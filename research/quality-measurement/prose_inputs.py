"""Isolated drafting/paragraph-editing trial. Never imported by production.

See prose-inputs/PREREG.md and RUNBOOK.md. Outputs stay under runs/. No scores,
candidate selection, manuscript writes or automatic retries are implemented here.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any

from litharness.domain import house
from litharness.domain.generation import CompletionRequest

ROOT = Path(__file__).resolve().parents[2]
REGISTRATION = ROOT / "research/quality-measurement/prose-inputs/PREREG.md"
MODEL = "claude-opus-5"
PLAIN_GUIDANCE = (
    "Write the scene from the stated viewpoint. Use concrete language and clear sentence "
    "references. Develop the planned action and its consequences. Keep explanations "
    "proportional to what the character needs to understand or decide."
)
PLAN_SECTIONS = ("starting_situation", "ordered_actions", "ending_state", "constraints")
FACT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["text", "source_quote"],
    "properties": {"text": {"type": "string"}, "source_quote": {"type": "string"}},
}
FACTUAL_PLAN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": list(PLAN_SECTIONS),
    "properties": {key: {"type": "array", "items": FACT} for key in PLAN_SECTIONS},
}
EDIT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["edits"],
    "properties": {
        "edits": {
            "type": "array",
            "maxItems": 6,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["paragraph", "original", "replacement"],
                "properties": {
                    "paragraph": {"type": "integer"},
                    "original": {"type": "string"},
                    "replacement": {"type": "string"},
                },
            },
        }
    },
}
ARMS = ("current_original", "plain_original", "current_factual", "plain_factual")
# Counterbalance order by replicate. Positions are fixed before outputs exist.
ORDER = tuple((arm, 1) for arm in ARMS) + tuple((arm, 2) for arm in reversed(ARMS))
MAX_CALLS = 11
SPEND_STOP_USD = 11.5


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def factual_request(statement: str) -> CompletionRequest:
    return CompletionRequest(
        system=(
            "Convert the supplied scene plan to factual planning notes. Keep every story "
            "decision, action, causal link, temporal relation, quantity, named person, visible "
            "detail and required unresolved question. Add no event or knowledge. Use short "
            "literal statements, not narration, metaphors, dialogue samples or commentary "
            "about readers. Keep actions in their original order. Attach an exact source_quote "
            "from the plan to each note for traceability. Those quotes will not reach drafting."
        ),
        prompt=statement,
        schema=FACTUAL_PLAN_SCHEMA,
        model=MODEL,
        max_output_tokens=5000,
        timeout_seconds=300.0,
        profile="trial.factual-plan.v1",
    )


def render_factual(payload: Any, source: str) -> str:
    if not isinstance(payload, dict) or set(payload) != set(PLAN_SECTIONS):
        raise ValueError("factual plan sections are missing or unexpected")
    blocks = []
    for key in PLAN_SECTIONS:
        rows = payload[key]
        if not isinstance(rows, list) or (key != "constraints" and not rows):
            raise ValueError(f"empty or malformed {key}")
        lines = []
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"text", "source_quote"}:
                raise ValueError("malformed factual note")
            if not isinstance(row["text"], str) or not row["text"].strip():
                raise ValueError("empty factual note")
            quote = row["source_quote"]
            if not isinstance(quote, str) or not quote.strip() or quote not in source:
                raise ValueError("source quote not found in original plan")
            lines.append(f"- {row['text'].strip()}")
        blocks.append(f"{key.replace('_', ' ').capitalize()}:\n" + "\n".join(lines))
    return "\n\n".join(blocks)


def draft_request(base: dict[str, str], factual: str, arm: str) -> CompletionRequest:
    if arm not in ARMS:
        raise ValueError("unknown arm")
    system, prompt = base["system"], base["prompt"]
    if system.count(house.HOUSE_RULES) != 1 or prompt.count("This scene: ") != 1:
        raise ValueError("saved prompt does not have the expected unambiguous boundaries")
    if arm.startswith("plain_"):
        system = system.replace(house.HOUSE_RULES, PLAIN_GUIDANCE, 1)
    if arm.endswith("_factual"):
        prefix, _ = prompt.split("This scene: ")
        prompt = prefix + "This scene: " + factual
    return CompletionRequest(
        system=system,
        prompt=prompt,
        model=MODEL,
        max_output_tokens=5000,
        timeout_seconds=300.0,
        profile="trial.prose-inputs.v1",
    )


def edit_request(scene: str) -> CompletionRequest:
    paragraphs = scene.strip().split("\n\n")
    return CompletionRequest(
        system=(
            "Edit the opening paragraphs of this scene. Address strained comparisons, "
            "redundant explanatory commentary and fragmented lists of incidental details "
            "where they obstruct the action. Preserve useful detail and the narrator's "
            "attitude. These are problems to consider, not sentence patterns to ban. "
            "You may edit only paragraphs 1 through 6; leave other paragraphs untouched. "
            "Keep each replacement a single paragraph. Preserve all events, their order, "
            "causal relationships, quantities, negation, uncertainty and who knows what. "
            "Do not add an action, motive or fact. Preserve printed system text verbatim. "
            "Return only changed paragraphs with their original text copied exactly. "
            "An empty edits list is allowed."
        ),
        prompt=json.dumps(
            {
                "paragraphs": [
                    {"paragraph": index, "text": text} for index, text in enumerate(paragraphs, 1)
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        schema=EDIT_SCHEMA,
        model=MODEL,
        max_output_tokens=5000,
        timeout_seconds=300.0,
        profile="trial.paragraph-editor.v1",
    )


def apply_edits(scene: str, payload: Any) -> str:
    """Enforce edit location and source identity. This does not certify semantic fidelity."""
    if not isinstance(payload, dict) or set(payload) != {"edits"}:
        raise ValueError("malformed edits object")
    edits = payload["edits"]
    if not isinstance(edits, list) or len(edits) > 6:
        raise ValueError("too many or malformed edits")
    paragraphs = scene.strip().split("\n\n")
    seen: set[int] = set()
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) != {"paragraph", "original", "replacement"}:
            raise ValueError("malformed paragraph edit")
        index = edit["paragraph"]
        if type(index) is not int or not 1 <= index <= min(6, len(paragraphs)) or index in seen:
            raise ValueError("paragraph outside scope or repeated")
        if edit["original"] != paragraphs[index - 1]:
            raise ValueError("original paragraph does not match")
        replacement = edit["replacement"]
        if not isinstance(replacement, str) or not replacement.strip() or "\n" in replacement:
            raise ValueError("replacement must be one nonempty paragraph")
        seen.add(index)
        paragraphs[index - 1] = replacement
    return "\n\n".join(paragraphs)


def prepare(
    out: Path, source_request: Path, source_scene: Path, reviewed_plan: Path | None = None
) -> None:
    if (
        not out.resolve().is_relative_to((ROOT / "runs").resolve())
        or out.resolve() == ROOT / "runs"
    ):
        raise ValueError("trial output must be a new directory beneath runs/")
    out.mkdir(parents=True, exist_ok=False)
    base = read_json(source_request)
    # Apply the landed knowledge-label correction equally to all four conditions. The
    # original source request and its digest are also retained, so this is not a fake replay.
    original = dict(base)
    base["system"] = base["system"].replace(
        "World rules and limits — established facts, subject to author locks. ",
        "World rules and limits — established facts, subject to author locks; "
        "their presence here does not mean a character knows them. ",
    )
    # The saved request is already a concrete POV request; preserve its identifier.
    label = "Established facts known to "
    if label in base["prompt"]:
        before, after = base["prompt"].split(label, 1)
        pov, rest = after.split(":\n", 1)
        base["prompt"] = (
            before + f"Established facts (POV: {pov}) — world truth, "
            "not automatically character knowledge:\n" + rest
        )
    source = source_scene.read_text(encoding="utf-8").strip()
    reviewed = read_json(reviewed_plan) if reviewed_plan is not None else None
    if reviewed is not None:
        render_factual(reviewed, base["prompt"].split("This scene: ")[1])
    manifest = {
        "version": 1,
        "code_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "registration_sha256": hashlib.sha256(REGISTRATION.read_bytes()).hexdigest(),
        "source_request": str(source_request.resolve()),
        "original_request": original,
        "base": base,
        "base_digest": digest(base),
        "original_digest": digest(original),
        "source_scene": source,
        "source_scene_digest": digest(source),
        "reviewed_plan": reviewed,
        "reviewed_plan_digest": digest(reviewed),
        "order": ORDER,
        "max_calls": MAX_CALLS,
        "spend_stop_usd": SPEND_STOP_USD,
        "model": MODEL,
    }
    write_new(out / "manifest.json", manifest)


def complete_once(out: Path, name: str, request: CompletionRequest) -> dict[str, Any]:
    from litharness.providers.cli import ClaudeCodeProvider

    frozen = json.loads(json.dumps(asdict(request)))
    request_path, result_path = out / f"{name}.request.json", out / f"{name}.result.json"
    if request_path.exists():
        if read_json(request_path) != frozen:
            raise ValueError("request changed; use a new trial")
        if not result_path.exists():
            raise RuntimeError("prior call has no recorded result; no automatic retry")
        return read_json(result_path)
    if os.environ.get("LITHARNESS_ENV") == "test":
        raise RuntimeError("live trial is disabled in tests")
    recorded = [read_json(path) for path in out.glob("*.result.json")]
    costs = [result["cost_usd"] for result in recorded]
    if len(list(out.glob("*.request.json"))) >= MAX_CALLS:
        raise RuntimeError("call cap reached")
    if any(cost is None for cost in costs) or sum(costs) >= SPEND_STOP_USD:
        raise RuntimeError("spend boundary reached or usage unavailable")
    write_new(request_path, frozen)
    print(f"START {name}", flush=True)
    try:
        result = ClaudeCodeProvider().complete(request)
    except Exception as error:
        write_new(out / f"{name}.error.json", {"type": type(error).__name__, "error": str(error)})
        raise
    envelope = asdict(result)
    write_new(result_path, envelope)
    with (out / f"{name}.txt").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(result.text + "\n")
    print(f"DONE {name}: {result.wall_ms / 1000:.1f}s, ${result.cost_usd} equivalent", flush=True)
    return envelope


def run(out: Path, phase: str) -> None:
    manifest = read_json(out / "manifest.json")
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != manifest["script_sha256"]:
        raise ValueError("script changed after prepare")
    if hashlib.sha256(REGISTRATION.read_bytes()).hexdigest() != manifest["registration_sha256"]:
        raise ValueError("registration changed after prepare")
    base = manifest["base"]
    if digest(base) != manifest["base_digest"]:
        raise ValueError("frozen input changed")
    if digest(manifest["source_scene"]) != manifest["source_scene_digest"]:
        raise ValueError("frozen editing source changed")
    statement = base["prompt"].split("This scene: ")[1]
    reviewed = manifest.get("reviewed_plan")
    if reviewed is not None:
        if digest(reviewed) != manifest["reviewed_plan_digest"]:
            raise ValueError("frozen reviewed plan changed")
        payload = reviewed
    else:
        payload = complete_once(out, "factual-plan", factual_request(statement))["parsed"]
    factual = render_factual(payload, statement)
    if phase == "plan":
        print(factual, flush=True)
        return
    # The plan is inspected for changed decisions before this phase is explicitly run.
    for arm, replicate in ORDER:
        complete_once(out, f"{arm}-{replicate}", draft_request(base, factual, arm))
    if phase == "draft":
        return
    for name, scene in (
        ("edit-original", manifest["source_scene"]),
        ("edit-plain-factual-1", read_json(out / "plain_factual-1.result.json")["text"]),
    ):
        result = complete_once(out, name, edit_request(scene))
        edited = apply_edits(scene, result["parsed"])
        target = out / f"{name}.scene.txt"
        if not target.exists():
            target.write_text(edited + "\n", encoding="utf-8", newline="\n")
            diff = difflib.unified_diff(
                scene.splitlines(True),
                edited.splitlines(True),
                fromfile="original",
                tofile="edited",
            )
            (out / f"{name}.diff").write_text("".join(diff), encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "plan", "draft", "edit"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-request", type=Path)
    parser.add_argument("--source-scene", type=Path)
    parser.add_argument("--reviewed-plan", type=Path)
    args = parser.parse_args()
    if args.phase == "prepare":
        if args.source_request is None or args.source_scene is None:
            parser.error("prepare requires --source-request and --source-scene")
        prepare(args.out, args.source_request, args.source_scene, args.reviewed_plan)
    else:
        run(args.out, args.phase)


if __name__ == "__main__":
    main()
