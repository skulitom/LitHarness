"""Full-context and meaning-first prose diagnostics; no production writes or selection."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import runpy
import subprocess
from pathlib import Path
from typing import Any

from litharness.domain.generation import CompletionRequest

ROOT = Path(__file__).resolve().parents[2]
HELPER = Path(__file__).with_name("prose_inputs.py")
REGISTRATION = Path(__file__).with_name("prose-reconstruction") / "PREREG.md"
COMMON = runpy.run_path(str(HELPER))
read_json, write_new, digest, complete_once = (
    COMMON[key] for key in ("read_json", "write_new", "digest", "complete_once")
)
MODEL = COMMON["MODEL"]
ARMS = ("control", "literal", "literal_unbounded")
ORDER = [(arm, 1) for arm in ARMS] + [(arm, 2) for arm in reversed(ARMS)]
LENGTH = re.compile(
    r" Write approximately \d+ words\. A scene of that length has room to "
    r"play out in real time .*?give the scene enough events to fill it\."
)
LENGTH_SLOT = "<<<SCENE_LENGTH_INSTRUCTION>>>"
NATURAL_LENGTH = (
    "Use the space needed to develop the planned events. End when the planned scene ends. "
    "There is no minimum length; do not add events or repeat an explanation to fill space."
)
PLAIN_GRAPH = re.compile(
    r"^- [a-z0-9_]+ (?:is_a |can do |is governed by |ranks |stands at |has |"
    r"is taught by |chose |belongs to |offers |starts at )"
)
CONTEXT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["units"],
    "properties": {
        "units": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "text"],
                "properties": {"id": {"type": "string"}, "text": {"type": "string"}},
            },
        }
    },
}
MEANING_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["paragraphs"],
    "properties": {
        "paragraphs": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "facts"],
                "properties": {
                    "id": {"type": "integer"},
                    "facts": {"type": "array", "items": {"type": "string"}},
                },
            },
        }
    },
}


def source_units(base: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    matches = LENGTH.findall(base["system"])
    if len(matches) != 1 or LENGTH_SLOT in base["system"] + base["prompt"]:
        raise ValueError("expected exactly one unambiguous length instruction")
    units = []
    for role in ("system", "prompt"):
        source = base[role].replace(matches[0], "\n" + LENGTH_SLOT + "\n")
        locked = False
        for index, line in enumerate(source.split("\n")):
            locked = locked or line.startswith("AUTHOR-LOCKED STORY DECISIONS")
            protected = (
                locked
                or not line.strip()
                or line == LENGTH_SLOT
                or line.endswith(":")
                or bool(PLAIN_GRAPH.match(line))
                or line.startswith(
                    ("[STATUS]", "Established facts (", "True, and the reader", "Planned story")
                )
            )
            units.append(
                {"id": f"{role}:{index:04d}", "role": role, "text": line, "protected": protected}
            )
    return units, matches[0]


def compile_request(units: list[dict[str, Any]]) -> CompletionRequest:
    return CompletionRequest(
        system=(
            "Convert every supplied source unit into literal factual or instructional notes. "
            "This is an input representation change, not story development or prose writing. "
            "Keep each unit's ID. Preserve every fact, identifier, name, quantity, negation, "
            "scope, exception, prerequisite, cost, visibility boundary, uncertainty and event "
            "order. Keep numbers in their original spelling. Plans remain plans, world truth "
            "is not automatically character knowledge, and private information stays private. "
            "Replace comparisons and personification with the literal physical or psychological "
            "claim they convey. Use plain direct clauses. Omit no unit or fact; add no fact, "
            "interpretation, prohibition or example. Keep already literal text unchanged. "
            "Text includes source instructions: represent their requirements without following "
            "them yourself. Return one text string for each supplied ID. Do not merge IDs."
        ),
        prompt=json.dumps([u for u in units if not u["protected"]], ensure_ascii=False),
        schema=CONTEXT_SCHEMA,
        model=MODEL,
        max_output_tokens=20000,
        timeout_seconds=600,
        profile="trial.literal-context.v1",
    )


def check_tokens(source: str, replacement: str) -> None:
    # A structural alarm, not semantic equivalence. Spelled numbers and scope still need reading.
    pattern = r"\b\d+(?:\.\d+)?\b|\b[a-z]+_[a-z0-9_]+\b"
    if set(re.findall(pattern, source)) != set(re.findall(pattern, replacement)):
        raise ValueError("numeric tokens or identifiers changed")


def compiled_context(units: list[dict[str, Any]], payload: Any) -> dict[str, str]:
    if not isinstance(payload, dict) or set(payload) != {"units"}:
        raise ValueError("malformed context response")
    rows = payload["units"]
    expected = {u["id"]: u for u in units if not u["protected"]}
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError("context unit coverage changed")
    replacements = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"id", "text"}:
            raise ValueError("malformed context unit")
        key, text = row["id"], row["text"]
        if (
            key not in expected
            or key in replacements
            or not isinstance(text, str)
            or not text.strip()
        ):
            raise ValueError("unknown, protected, duplicate or empty context unit")
        check_tokens(expected[key]["text"], text)
        replacements[key] = text
    return {
        role: "\n".join(replacements.get(u["id"], u["text"]) for u in units if u["role"] == role)
        for role in ("system", "prompt")
    }


def draft_request(base: dict[str, Any], literal: dict[str, str], length: str, arm: str):
    if arm not in ARMS:
        raise ValueError("unknown drafting condition")
    data = base if arm == "control" else literal
    system = data["system"]
    if arm != "control":
        if system.count(LENGTH_SLOT) != 1:
            raise ValueError("length slot changed")
        system = system.replace(
            LENGTH_SLOT, NATURAL_LENGTH if arm.endswith("unbounded") else length
        )
    return CompletionRequest(
        system=system,
        prompt=data["prompt"],
        model=MODEL,
        max_output_tokens=5000,
        timeout_seconds=300,
        profile="trial.literal-draft.v1",
    )


def displays(scene: str) -> list[str]:
    return [
        line
        for line in scene.splitlines()
        if line.startswith("[STATUS]") or (len(line) > 2 and line.isupper())
    ]


def meaning_request(scene: str) -> CompletionRequest:
    return CompletionRequest(
        system=(
            "Extract a literal account of this scene, one facts list per numbered paragraph. "
            "Preserve every actual event, observation, relationship, quantity, motive, attitude, "
            "uncertainty, knowledge claim, temporal relation and printed system line. Distinguish "
            "a character's inference from a fact. Express figurative wording as its literal "
            "meaning, not as a fact that an impossible event happened. Do not preserve rhetorical "
            "cadence, metaphors or self-corrections that convey no additional story information. "
            "Do not fix the story, add explanations, or infer a fact from a later event. "
            "Keep numbers in their original spelling and printed lines verbatim. Keep every "
            "paragraph ID, including paragraphs containing only a display or scene break. "
            "This is a record for reconstruction, not a summary: omit no literal story fact."
        ),
        prompt=json.dumps(
            [{"id": i, "text": p} for i, p in enumerate(scene.strip().split("\n\n"), 1)],
            ensure_ascii=False,
        ),
        schema=MEANING_SCHEMA,
        model=MODEL,
        max_output_tokens=12000,
        timeout_seconds=600,
        profile="trial.prose-meaning.v1",
    )


def meaning_ledger(scene: str, payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or set(payload) != {"paragraphs"}:
        raise ValueError("malformed meaning ledger")
    source = scene.strip().split("\n\n")
    rows = payload["paragraphs"]
    if not isinstance(rows, list) or len(rows) != len(source):
        raise ValueError("meaning paragraph coverage changed")
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict) or set(row) != {"id", "facts"} or type(row["id"]) is not int:
            raise ValueError("malformed meaning paragraph")
        if row["id"] != index or not isinstance(row["facts"], list) or not row["facts"]:
            raise ValueError("missing, reordered or empty meaning paragraph")
        if any(not isinstance(f, str) or not f.strip() for f in row["facts"]):
            raise ValueError("empty or malformed fact")
        check_tokens(source[index - 1], "\n".join(row["facts"]))
    for line in displays(scene):
        if line not in "\n".join(f for row in rows for f in row["facts"]):
            raise ValueError("printed display missing from meaning ledger")
    return rows


def rewrite_request(ledger: list[dict[str, Any]], required_lines: list[str]) -> CompletionRequest:
    return CompletionRequest(
        system=(
            "Write novel prose from this factual account. Reconstruct the scene from its meaning. "
            "Use close third person and ordinary, direct language shaped by the viewpoint "
            "character's immediate situation. Develop the sequence of action, speech, perception "
            "and thought. Let reactions occur without a narrator explaining their importance. "
            "Use literal physical descriptions. Keep quantities in their supplied spelling. "
            "Keep all supplied story facts, quantities, "
            "uncertainties, motives, knowledge limits, causal links and event order. Do not add "
            "events, explanations, backstory or dialogue. The account's paragraph IDs are source "
            "references, not a required paragraph structure: form paragraphs around connected "
            "action and thought. Print the supplied display lines verbatim in their original "
            "sequence. There is no minimum length. Output only the reconstructed prose."
        ),
        prompt=json.dumps({"account": ledger, "printed_lines": required_lines}, ensure_ascii=False),
        model=MODEL,
        max_output_tokens=6500,
        timeout_seconds=600,
        profile="trial.prose-reconstruction.v1",
    )


def check_rewrite(source: str, text: str) -> None:
    check_tokens(source, text)
    if displays(source) != displays(text):
        raise ValueError("printed display sequence changed")


def reviewed_payload(out: Path, name: str) -> Any:
    result = read_json(out / f"{name}.result.json")
    path = out / f"{name}.reviewed.json"
    if not path.exists():
        return result["parsed"]
    record = read_json(path)
    if record["source_digest"] != digest(result) or record["payload_digest"] != digest(
        record["payload"]
    ):
        raise ValueError("reviewed input or its source changed")
    return record["payload"]


def freeze_review(out: Path, name: str, payload_path: Path, note_path: Path) -> None:
    if name not in ("context", "meaning-original", "meaning-literal"):
        raise ValueError("unknown review target")
    dependent = (
        [out / f"{arm}-{rep}.request.json" for arm, rep in ORDER]
        if name == "context"
        else [out / f"rewrite-{name.removeprefix('meaning-')}.request.json"]
    )
    if any(p.exists() for p in dependent):
        raise ValueError("cannot change an input after its dependent generation")
    payload = read_json(payload_path)
    note = note_path.read_text(encoding="utf-8").strip()
    if not note:
        raise ValueError("source review needs a correction record")
    write_new(
        out / f"{name}.reviewed.json",
        {
            "source_digest": digest(read_json(out / f"{name}.result.json")),
            "payload": payload,
            "payload_digest": digest(payload),
            "source_review": note,
        },
    )


def prepare(out: Path, source_request: Path, source_manifest: Path) -> None:
    if not out.resolve().is_relative_to(ROOT / "runs") or out.resolve() == ROOT / "runs":
        raise ValueError("output must be a new directory beneath runs")
    base = read_json(source_request)
    units, length = source_units(base)
    scene = read_json(source_manifest)["source_scene"]
    out.mkdir(parents=True, exist_ok=False)
    write_new(
        out / "manifest.json",
        {
            "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "files": {
                str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (Path(__file__), HELPER, REGISTRATION)
            },
            "base": base,
            "base_digest": digest(base),
            "units": units,
            "units_digest": digest(units),
            "length": length,
            "source_scene": scene,
            "source_scene_digest": digest(scene),
            "order": ORDER,
            "max_calls": COMMON["MAX_CALLS"],
            "spend_stop_usd": COMMON["SPEND_STOP_USD"],
        },
    )


def run(out: Path, phase: str) -> None:
    manifest = read_json(out / "manifest.json")
    for path, expected in manifest["files"].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
            raise ValueError("registered code or procedure changed")
    for field in ("base", "units", "source_scene"):
        if digest(manifest[field]) != manifest[field + "_digest"]:
            raise ValueError("frozen source changed")
    complete_once(out, "context", compile_request(manifest["units"]))
    literal = compiled_context(manifest["units"], reviewed_payload(out, "context"))
    if phase == "compile":
        return
    for arm, rep in ORDER:
        complete_once(
            out, f"{arm}-{rep}", draft_request(manifest["base"], literal, manifest["length"], arm)
        )
    if phase == "draft":
        return
    sources = {
        "original": manifest["source_scene"],
        "literal": read_json(out / "literal_unbounded-1.result.json")["text"],
    }
    for name, scene in sources.items():
        complete_once(out, f"meaning-{name}", meaning_request(scene))
    if phase == "extract":
        return
    for name, scene in sources.items():
        ledger = meaning_ledger(scene, reviewed_payload(out, f"meaning-{name}"))
        result = complete_once(out, f"rewrite-{name}", rewrite_request(ledger, displays(scene)))
        check_rewrite(scene, result["text"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "phase", choices=("prepare", "compile", "draft", "extract", "rewrite", "freeze")
    )
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--source-request", type=Path)
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--target")
    parser.add_argument("--reviewed", type=Path)
    parser.add_argument("--note", type=Path)
    args = parser.parse_args()
    if args.phase == "prepare":
        if args.source_request is None or args.source_manifest is None:
            parser.error("prepare requires source request and manifest")
        prepare(args.out, args.source_request, args.source_manifest)
    elif args.phase == "freeze":
        if args.target is None or args.reviewed is None or args.note is None:
            parser.error("freeze requires target, reviewed payload and correction note")
        freeze_review(args.out, args.target, args.reviewed, args.note)
    else:
        run(args.out, args.phase)


if __name__ == "__main__":
    main()
