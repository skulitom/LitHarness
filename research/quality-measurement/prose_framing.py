"""Compare transport framing, writer persona, and source-selected scene context."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import runpy
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any

from litharness.domain.generation import CompletionRequest
from litharness.providers.cli import ClaudeCodeProvider, subprocess_runner

ROOT = Path(__file__).resolve().parents[2]
HELPER = Path(__file__).with_name("prose_inputs.py")
REGISTRATION = Path(__file__).with_name("prose-framing") / "PREREG.md"
COMMON = runpy.run_path(str(HELPER))
read_json, write_new, digest = (COMMON[k] for k in ("read_json", "write_new", "digest"))
MODEL = "claude-opus-5"
ARMS = ("control", "isolated", "neutral", "focused")
ORDER = [(a, 1) for a in ARMS] + [(a, 2) for a in reversed(ARMS)]
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["decisions"],
    "properties": {
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "keep", "reason"],
                "properties": {
                    "id": {"type": "string"},
                    "keep": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
            },
        }
    },
}


def source_blocks(prompt: str) -> list[dict[str, Any]]:
    """Keep section authority with its text; cast paragraphs remain indivisible."""
    blocks = []
    planned = False
    for index, paragraph in enumerate(prompt.split("\n\n")):
        planned = planned or paragraph.startswith("Now write ")
        if planned or paragraph.startswith("True, and the reader has not been told"):
            header, lines, mandatory = "", [paragraph], True
        elif paragraph.startswith(("Planned story", "Open threads", "Established facts")):
            header, *lines = paragraph.split("\n")
            mandatory = False
        else:
            header, lines, mandatory = "", [paragraph], False
        blocks.append(
            {
                "header": header,
                "units": [
                    {"id": f"b{index}:u{i}", "text": line, "mandatory": mandatory}
                    for i, line in enumerate(lines)
                ],
            }
        )
    if sum(b["units"][0]["text"].startswith("Now write ") for b in blocks) != 1:
        raise ValueError("expected one scene-plan boundary")
    return blocks


def selected_prompt(blocks: list[dict[str, Any]], payload: Any) -> str:
    expected = {u["id"] for b in blocks for u in b["units"] if not u["mandatory"]}
    if not isinstance(payload, dict) or set(payload) != {"decisions"}:
        raise ValueError("malformed selection")
    rows = payload["decisions"]
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError("selection coverage changed")
    choices = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"id", "keep", "reason"}:
            raise ValueError("malformed decision")
        if row["id"] not in expected or row["id"] in choices or type(row["keep"]) is not bool:
            raise ValueError("unknown, protected, duplicate or invalid decision")
        if not isinstance(row["reason"], str) or not row["reason"].strip():
            raise ValueError("missing selection reason")
        choices[row["id"]] = row["keep"]
    rendered = []
    for block in blocks:
        lines = [u["text"] for u in block["units"] if u["mandatory"] or choices[u["id"]]]
        if lines:
            rendered.append("\n".join(([block["header"]] if block["header"] else []) + lines))
    return "\n\n".join(rendered)


def selection_request(base: dict[str, Any], blocks: list[dict[str, Any]]) -> CompletionRequest:
    return CompletionRequest(
        system=(
            "Select source context for the current scene. Return one keep/drop decision and "
            "short reason for every non-mandatory source ID. Select facts needed to stage the "
            "planned events, identify their actors, preserve causes and knowledge boundaries, "
            "and describe the immediate place and system consistently. Keep relevant costs, "
            "prerequisites, exceptions and physical constraints. Drop future plot summaries, "
            "unneeded future actors, distant progression details and duplicate statements when "
            "their needed information is already retained. The complete supplied system rules, "
            "author locks, private-information block and current scene plan remain mandatory "
            "and will reach the writer unchanged. Select only; do not rewrite or add prose. "
            "Your reasons will not reach the writer. There is no token or selection quota."
        ),
        prompt=json.dumps(
            {"system_constraints": base["system"], "blocks": blocks}, ensure_ascii=False
        ),
        schema=SCHEMA,
        model=MODEL,
        max_output_tokens=12000,
        timeout_seconds=600,
        profile="trial.prose-framing.selection.v1",
    )


def draft_request(base: dict[str, Any], focused: str, arm: str) -> CompletionRequest:
    if arm not in ARMS:
        raise ValueError("unknown arm")
    system = base["system"]
    if arm in ("neutral", "focused"):
        _, separator, system = system.partition("\n\n")
        if not separator or not system.startswith("You are drafting one scene of a novel."):
            raise ValueError("writer persona boundary changed")
    return CompletionRequest(
        system=system,
        prompt=focused if arm == "focused" else base["prompt"],
        model=MODEL,
        max_output_tokens=5000,
        timeout_seconds=600,
        profile=f"trial.prose-framing.{arm}.v1",
    )


def transport_argv(argv: list[str], isolated: bool) -> list[str]:
    result = list(argv)
    if isolated:
        if "--tools" not in result or result[result.index("--tools") + 1] != "":
            raise ValueError("isolated trial requires no built-in tools")
        if result.count("--append-system-prompt") != 1:
            raise ValueError("expected exactly one nonempty system prompt")
        result[result.index("--append-system-prompt")] = "--system-prompt"
        result.append("--safe-mode")
    return result


def complete_once(out: Path, name: str, request: CompletionRequest, isolated: bool):
    argv = transport_argv(ClaudeCodeProvider()._argv(request), isolated)
    frozen = {"request": asdict(request), "isolated": isolated, "argv": argv}
    frozen = json.loads(json.dumps(frozen))
    request_path, result_path = out / f"{name}.request.json", out / f"{name}.result.json"
    if request_path.exists():
        if read_json(request_path) != frozen:
            raise ValueError("request or transport changed")
        if not result_path.exists():
            raise RuntimeError("missing recorded response; no automatic retry")
        return read_json(result_path)
    if os.environ.get("LITHARNESS_ENV") == "test":
        raise RuntimeError("live trial is disabled in tests")
    costs = [read_json(p)["cost_usd"] for p in out.glob("*.result.json")]
    if len(list(out.glob("*.request.json"))) >= 9:
        raise RuntimeError("nine-call limit reached")
    if any(c is None for c in costs) or sum(costs) >= 6.0:
        raise RuntimeError("spend boundary reached or usage unavailable")
    write_new(request_path, frozen)

    def runner(actual, *, timeout, cwd=None, stdin=None):
        actual = transport_argv(list(actual), isolated)
        if actual != argv:
            raise ValueError("executed argv differs from frozen argv")
        return subprocess_runner(actual, timeout=timeout, cwd=cwd, stdin=stdin)

    print(f"START {name}", flush=True)
    try:
        result = ClaudeCodeProvider(runner=runner).complete(request)
    except Exception as error:
        write_new(out / f"{name}.error.json", {"type": type(error).__name__, "error": str(error)})
        raise
    envelope = asdict(result)
    write_new(result_path, envelope)
    (out / f"{name}.txt").write_text(result.text + "\n", encoding="utf-8", newline="\n")
    print(f"DONE {name}: {result.wall_ms / 1000:.1f}s, ${result.cost_usd} equivalent", flush=True)
    return envelope


def prepare(out: Path, source: Path) -> None:
    if not out.resolve().is_relative_to(ROOT / "runs") or out.resolve() == ROOT / "runs":
        raise ValueError("output must be a new directory beneath runs")
    base = read_json(source)
    blocks = source_blocks(base["prompt"])
    out.mkdir(parents=True, exist_ok=False)
    write_new(
        out / "manifest.json",
        {
            "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "cli_version": subprocess.check_output(["claude", "--version"], text=True).strip(),
            "files": {
                str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (
                    Path(__file__),
                    HELPER,
                    REGISTRATION,
                    ROOT / "src/litharness/providers/cli.py",
                    ROOT / "src/litharness/domain/generation.py",
                )
            },
            "base": base,
            "base_digest": digest(base),
            "blocks": blocks,
            "blocks_digest": digest(blocks),
            "order": ORDER,
            "max_calls": 9,
            "spend_stop_usd": 6.0,
        },
    )


def run(out: Path, phase: str, reviewed: Path | None, note: Path | None) -> None:
    manifest = read_json(out / "manifest.json")
    for path, expected in manifest["files"].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
            raise ValueError("registered code or procedure changed")
    for field in ("base", "blocks"):
        if digest(manifest[field]) != manifest[field + "_digest"]:
            raise ValueError("frozen input changed")
    base, blocks = manifest["base"], manifest["blocks"]
    result = complete_once(out, "selection", selection_request(base, blocks), True)
    if phase == "select":
        return
    path = out / "selection.reviewed.json"
    if phase == "freeze":
        if reviewed is None or note is None:
            raise ValueError("freeze requires reviewed decisions and a source-review note")
        if any((out / f"{a}-{r}.request.json").exists() for a, r in ORDER):
            raise ValueError("cannot change context after dependent drafting")
        payload, rationale = read_json(reviewed), note.read_text(encoding="utf-8").strip()
        selected_prompt(blocks, payload)
        if not rationale:
            raise ValueError("empty source-review note")
        write_new(
            path,
            {
                "source_digest": digest(result),
                "payload": payload,
                "payload_digest": digest(payload),
                "source_review": rationale,
            },
        )
        return
    record = read_json(path)
    if record["source_digest"] != digest(result) or record["payload_digest"] != digest(
        record["payload"]
    ):
        raise ValueError("reviewed selection changed")
    focused = selected_prompt(blocks, record["payload"])
    for arm, rep in ORDER:
        complete_once(out, f"{arm}-{rep}", draft_request(base, focused, arm), arm != "control")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "select", "freeze", "draft"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--reviewed", type=Path)
    parser.add_argument("--note", type=Path)
    args = parser.parse_args()
    if args.phase == "prepare":
        if args.source is None:
            parser.error("prepare requires a saved request")
        prepare(args.out, args.source)
    else:
        run(args.out, args.phase, args.reviewed, args.note)


if __name__ == "__main__":
    main()
