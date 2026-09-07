"""Source-derived attention used as background versus operative focus; research only."""

from __future__ import annotations

import argparse
import json
import runpy
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
BASE = runpy.run_path(str(HERE / "prose_constraint_levels.py"))
CODEX = BASE["CODEX"]
read, write_new, sha = (CODEX[k] for k in ("read", "write_new", "sha"))
REG = HERE / "prose-attention"
ORDER = ("trace-1", "background-1", "operative-1", "operative-2", "background-2")
TOKEN_STOP = 95_000
TRACE_SYSTEM = """Derive a provisional attention trace from the supplied story source.
You are not judging prose, selecting a draft or planning new events. The original prose is
unavailable. For each supplied phase, infer a specific immediate concern compatible with
the protagonist's recorded situation, conduct and knowledge. Choose 1-3 source IDs in that
phase to foreground and 1-3 different IDs to leave peripheral. All source events still occur;
peripheral means less emphasis, not deletion or failure to perceive a required fact.
Identify one event in the phase that interrupts or redirects this attention, and one thing
that may remain unresolved in his attention as the phase ends. Let concerns develop across
phases. Avoid assigning generic virtues, biography, a diagnosis, symbols, moral lessons or a
new motive as established truth. These are compatible rendering possibilities, not new canon.
Use only knowledge available at the relevant time; later events cannot explain earlier focus.
Return only JSON: {"phases":[{"id":"supplied phase ID","concern":"up to 35 words",
"foreground":["source ID"],"peripheral":["source ID"],"shift":{"at":"source ID",
"pressure":"up to 25 words"},"unresolved":"up to 25 words","basis":["source ID"]}]}.
The basis IDs (1-5) must support the concern and come from this phase or earlier. Do not
write sample narration, dialogue, prose advice, a plot outline, a score or an explanation
outside this JSON. No source detail acquires a new identity or relationship."""
WRITER_SYSTEM = """Write the complete opening chapter as novel prose in close third person,
past tense. Aim for 1500-1800 words. Return only the chapter, without title or commentary.
The source_units are binding at their specified times. Preserve events, causal relations,
consequential quantities, viewpoint knowledge, scene division and endpoint. Interpretations
remain interpretations; do not turn unknown mechanics into facts or resolve ambiguities.
The required_narration IDs must reach the reader through action, dialogue or narration;
other units remain true but may be implicit. An event need not receive an explanation after
being shown. Paragraph organization, immediate gestures and dialogue are yours. Do not add
incidents, biography, identities, powers or rules. Display templates preserve wording when
each specified message occurs; preserve occurrence order, with punctuation fitting placement.
The attention_trace is a provisional source-based interpretation shared across this test.
It does not add facts, require its concern sentences to be narrated, or override knowledge
timing or required events. Its phases are source intervals, not section or paragraph quotas.
The rendering_mode specifies how to use that same trace. No particular sentence style,
ban on explanation, rhetorical pattern or concluding insight is prescribed."""
MODES = {
    "background": """Treat the trace as background understanding of the character during
these events. Compose the narration with your ordinary choices of focus, emphasis, duration
and transitions. The listed foreground/peripheral distinctions and shifts are available
interpretations, not directions governing those narrative choices.""",
    "operative": """Use the trace to govern the narration's focus, emphasis, duration and
transitions within each phase. Give the foreground detail attention through what the character
is trying to notice or do; let peripheral facts take only the space their causal role needs.
Carry the current concern until the specified pressure interrupts or redirects attention.
An unresolved concern may remain open when the next event demands attention. Realize this
allocation in the narration itself; the trace's labels do not need to be explained to
the reader.""",
}


def source_payload(source: Any) -> dict[str, Any]:
    if not isinstance(source, dict) or set(source) != {"chapter_source", "phases"}:
        raise ValueError("invalid attention source")
    chapter = source["chapter_source"]
    old = json.loads(BASE["BASE"]["compose"](chapter)["focused"]["prompt"].split("\n", 1)[1])
    phases = source["phases"]
    ids = [u["id"] for u in chapter["facts"]]
    if not isinstance(phases, list) or not phases:
        raise ValueError("empty phases")
    cursor = 0
    seen = set()
    for phase in phases:
        if (
            not isinstance(phase, dict)
            or set(phase) != {"id", "first", "last"}
            or any(not isinstance(v, str) or not v.strip() for v in phase.values())
            or phase["id"] in seen
            or phase["first"] not in ids
            or phase["last"] not in ids
            or ids.index(phase["first"]) != cursor
            or ids.index(phase["last"]) < cursor
        ):
            raise ValueError("phases must partition source in order")
        seen.add(phase["id"])
        cursor = ids.index(phase["last"]) + 1
    if cursor != len(ids):
        raise ValueError("incomplete phase coverage")
    # Shared punctuation normalization retains original message words and occurrences.
    old["display_templates"] = [s.rstrip("., ") for s in old.pop("literal_sequence")]
    old["phases"] = phases
    return old


def trace_request(source: Any) -> dict[str, str]:
    return {
        "system": TRACE_SYSTEM,
        "prompt": json.dumps(source_payload(source), ensure_ascii=False),
    }


def validate_trace(source: Any, trace: Any) -> None:
    source_payload(source)
    ids = [u["id"] for u in source["chapter_source"]["facts"]]
    if (
        not isinstance(trace, dict)
        or set(trace) != {"phases"}
        or not isinstance(trace["phases"], list)
    ):
        raise ValueError("invalid attention trace")
    if len(trace["phases"]) != len(source["phases"]):
        raise ValueError("trace phase count")
    for plan, row in zip(source["phases"], trace["phases"], strict=True):
        if (
            not isinstance(row, dict)
            or set(row)
            != {"id", "concern", "foreground", "peripheral", "shift", "unresolved", "basis"}
            or row["id"] != plan["id"]
        ):
            raise ValueError("invalid trace row")
        allowed = ids[ids.index(plan["first"]) : ids.index(plan["last"]) + 1]
        prior = ids[: ids.index(plan["last"]) + 1]
        for key, limit, pool in (
            ("foreground", 3, allowed),
            ("peripheral", 3, allowed),
            ("basis", 5, prior),
        ):
            value = row[key]
            if (
                not isinstance(value, list)
                or not 1 <= len(value) <= limit
                or any(not isinstance(i, str) or i not in pool for i in value)
                or len(set(value)) != len(value)
            ):
                raise ValueError("invalid or future attention reference")
        if set(row["foreground"]) & set(row["peripheral"]):
            raise ValueError("foreground and peripheral overlap")
        shift = row["shift"]
        if (
            not isinstance(shift, dict)
            or set(shift) != {"at", "pressure"}
            or shift["at"] not in allowed
        ):
            raise ValueError("invalid attention shift")
        for value, limit in (
            (row["concern"], 35),
            (row["unresolved"], 25),
            (shift["pressure"], 25),
        ):
            if not isinstance(value, str) or not 1 <= len(value.split()) <= limit:
                raise ValueError("invalid attention text length")


def writer_requests(source: Any, trace: Any) -> dict[str, Any]:
    validate_trace(source, trace)
    shared = {**source_payload(source), "attention_trace": trace}
    return {
        mode: {
            "system": WRITER_SYSTEM,
            "prompt": json.dumps({**shared, "rendering_mode": text}, ensure_ascii=False),
        }
        for mode, text in MODES.items()
    }


def quota(out: Path) -> int:
    requests = list(out.glob("*/full-1.request.json"))
    if any(p.parent.name not in ORDER for p in requests) or len(requests) > len(ORDER):
        raise ValueError("unregistered invocation")
    total = 0
    for path in out.glob("*/full-1.result.json"):
        result = read(path)
        if path.parent.name not in ORDER or result["status"] != "completed":
            raise RuntimeError("previous failure or unregistered result; no retry")
        for key in ("input_tokens", "output_tokens", "reasoning_output_tokens"):
            value = result["usage"].get(key, 0 if key == "reasoning_output_tokens" else None)
            if type(value) is not int or value < 0:
                raise ValueError("invalid usage")
            total += value
    if total >= TOKEN_STOP:
        raise RuntimeError("subscription token stop reached")
    return total


def prepare(out: Path, source_path: Path) -> None:
    if not out.is_relative_to(ROOT / "runs") or out == ROOT / "runs":
        raise ValueError("output must be beneath runs")
    source = read(source_path)
    request = trace_request(source)
    prefix = CODEX["command_prefix"]()
    auth = subprocess.run(
        [*prefix, "login", "status"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=CODEX["subscription_env"](),
        check=False,
    )
    if auth.returncode or (auth.stdout + auth.stderr).strip() != "Logged in using ChatGPT":
        raise RuntimeError("ChatGPT subscription required")
    out.mkdir(parents=True, exist_ok=False)
    systems = []
    for name in ORDER:
        folder = out / name
        (folder / "work").mkdir(parents=True)
        system = folder / "system.txt"
        system.write_text(
            TRACE_SYSTEM if name == "trace-1" else WRITER_SYSTEM, encoding="utf-8", newline="\n"
        )
        systems.append(system)
    files = [
        Path(__file__),
        *[
            HERE / p
            for p in (
                "prose_constraint_levels.py",
                "prose_narration_obligations.py",
                "prose_protected_reconstruction.py",
                "prose_paragraph_revision.py",
                "prose_codex.py",
            )
        ],
        REG / "PREREG.md",
        REG / "RUNBOOK.md",
        source_path,
        source_path.with_name("prepare_source.py"),
        source_path.with_name("source-review.md"),
        Path(prefix[1]),
        *systems,
    ]
    write_new(
        out / "manifest.json",
        {
            "source": source,
            "trace_request": request,
            "prefix": prefix,
            "order": ORDER,
            "files": {str(p): sha(p) for p in files},
            "token_stop": TOKEN_STOP,
            "authentication": "chatgpt",
            "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "cli_version": subprocess.check_output([*prefix, "--version"], text=True).strip(),
        },
    )


def call(out: Path, name: str, request: dict[str, str], manifest: dict[str, Any]) -> dict[str, Any]:
    quota(out)
    if name not in ORDER:
        raise ValueError("unregistered invocation")
    print(f"LOGICAL CALL {name}", flush=True)
    return CODEX["complete_once"](
        out / name, "full-1", {"prefix": manifest["prefix"], "requests": {"full": request}}
    )


def trace_phase(out: Path) -> None:
    manifest = CODEX["validate"](out)
    if manifest["trace_request"] != trace_request(manifest["source"]):
        raise ValueError("trace request changed")
    result = call(out, "trace-1", manifest["trace_request"], manifest)
    validate_trace(manifest["source"], json.loads(result["text"]))


def freeze(out: Path, review_path: Path) -> None:
    manifest = CODEX["validate"](out)
    trace_path = out / "trace-1/full-1.txt"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    result = read(out / "trace-1/full-1.result.json")
    if result["status"] != "completed" or json.loads(result["text"]) != trace:
        raise ValueError("trace/result mismatch")
    review = read(review_path)
    if (
        review.get("trace_sha256") != sha(trace_path)
        or review.get("source_compatible") is not True
        or review.get("future_knowledge_absent") is not True
        or review.get("no_new_canon") is not True
        or review.get("reviewed_phases") != [p["id"] for p in manifest["source"]["phases"]]
    ):
        raise ValueError("trace needs complete source review")
    files = [
        out / f"trace-1/full-1.{suffix}"
        for suffix in ("request.json", "raw.json", "result.json", "txt")
    ]
    files.append(review_path)
    write_new(
        out / "draft-manifest.json",
        {
            "trace": trace,
            "requests": writer_requests(manifest["source"], trace),
            "files": {str(p): sha(p) for p in files},
            "review": review,
        },
    )


def drafts(out: Path) -> None:
    for name in ORDER[1:]:
        manifest = CODEX["validate"](out)
        frozen = read(out / "draft-manifest.json")
        if any(sha(Path(p)) != h for p, h in frozen["files"].items()):
            raise ValueError("frozen trace or review changed")
        if frozen["requests"] != writer_requests(manifest["source"], frozen["trace"]):
            raise ValueError("writer requests changed")
        call(out, name, frozen["requests"][name.rsplit("-", 1)[0]], manifest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "trace", "freeze", "draft"))
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--review", type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    if args.phase == "prepare":
        if not args.source:
            parser.error("prepare requires --source")
        prepare(out, args.source.resolve())
    elif args.phase == "trace":
        trace_phase(out)
    elif args.phase == "freeze":
        if not args.review:
            parser.error("freeze requires --review")
        freeze(out, args.review.resolve())
    else:
        drafts(out)


if __name__ == "__main__":
    main()
