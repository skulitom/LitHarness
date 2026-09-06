"""Two registered subscription diagnostics: reasoning effort and future-source exposure."""

from __future__ import annotations

import argparse
import json
import runpy
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
CODEX = runpy.run_path(str(HERE / "prose_codex.py"))
PATCH = runpy.run_path(str(HERE / "prose_paragraph_revision.py"))
read, write_new, sha = (CODEX[k] for k in ("read", "write_new", "sha"))
REGISTRATION = HERE / "prose-reasoning-disclosure/PREREG.md"
ORDER = ("full-1", "focused-1", "focused-2", "full-2")
TOKEN_STOP = 180_000
CALL_LIMIT = 16
DISCLOSURE_SYSTEM = """Write the next installment of one continuous chapter as novel prose.
Use close third person, past tense. Preserve the supplied events, causes, temporal relations,
viewpoint knowledge, consequential quantities and unresolved ambiguities. Convey the required
meaning without separately explaining it after it is shown. Wording and paragraph organization
are yours. Do not add incidents, backstory, named characters, quantities or rules. Continue
directly from the previous prose, without rewriting, repeating or summarizing it. Draft only
the facts assigned to this installment. Stop after its last assigned event, without inventing
a closing reflection or preview. Available later source is reference only, not permission to
narrate future events or give the viewpoint character future knowledge. Preserve the current
installment's literal sequence exactly, including punctuation and repeated occurrences; an
inline literal may stay inline. Insert a scene separator after this installment only when
indicated. There is no word target or compression quota. Return only the new prose, without
a title, installment label, commentary or score."""


def validate_source(source: Any) -> None:
    if not isinstance(source, dict) or set(source) != {"original", "reasoning_request", "parts"}:
        raise ValueError("malformed source")
    PATCH["validate_source"](source["original"])
    request = source["reasoning_request"]
    if (
        not isinstance(request, dict)
        or set(request) != {"system", "prompt"}
        or any(not isinstance(v, str) or not v.strip() for v in request.values())
    ):
        raise ValueError("invalid reasoning request")
    parts = source["parts"]
    if not isinstance(parts, list) or len(parts) != 3:
        raise ValueError("three source installments required")
    ids, literals = [], []
    for part in parts:
        if not isinstance(part, dict) or set(part) != {"facts", "literals", "notes", "break_after"}:
            raise ValueError("malformed installment")
        if not isinstance(part["facts"], list) or not part["facts"]:
            raise ValueError("empty installment")
        if not isinstance(part["notes"], str) or type(part["break_after"]) is not bool:
            raise ValueError("invalid installment metadata")
        for fact in part["facts"]:
            if (
                not isinstance(fact, dict)
                or set(fact) != {"id", "text"}
                or any(not isinstance(v, str) or not v.strip() for v in fact.values())
            ):
                raise ValueError("invalid installment fact")
            ids.append(fact["id"])
        if not isinstance(part["literals"], list) or any(
            not isinstance(v, str) or not v for v in part["literals"]
        ):
            raise ValueError("invalid installment literals")
        literals.extend(part["literals"])
    if ids != [f["id"] for f in source["original"]["protected"]]:
        raise ValueError("installment coverage or order changed")
    expected = PATCH["literal_sequence"](source["original"]["text"], source["original"]["verbatim"])
    if literals != expected:
        raise ValueError("installment literal coverage or order changed")


def disclosure_request(source: Any, condition: str, stage: int, previous: str) -> dict[str, str]:
    validate_source(source)
    if condition not in {"full", "focused"} or type(stage) is not int or stage not in {1, 2, 3}:
        raise ValueError("unregistered disclosure condition or stage")
    if not isinstance(previous, str) or bool(previous.strip()) != (stage > 1):
        raise ValueError("previous prose does not match stage")
    part = source["parts"][stage - 1]
    shared = {
        "source_available_so_far": source["parts"][:stage],
        "write_now": [f["id"] for f in part["facts"]],
        "literal_sequence_now": part["literals"],
        "scene_division_after_installment": part["break_after"],
        "previous_prose": previous,
    }
    prompt = "Current installment:\n" + json.dumps(shared, ensure_ascii=False)
    if condition == "full" and stage < 3:
        prompt += "\n\nLater source, not to be drafted yet:\n" + json.dumps(
            source["parts"][stage:], ensure_ascii=False
        )
    return {"system": DISCLOSURE_SYSTEM, "prompt": prompt}


def quota(out: Path) -> int:
    total = 0
    for path in out.glob("calls/**/*.result.json"):
        result = read(path)
        if result["status"] != "completed":
            raise RuntimeError("previous transport failure; no further dispatch")
        for key in ("input_tokens", "output_tokens", "reasoning_output_tokens"):
            value = result["usage"].get(key, 0 if key == "reasoning_output_tokens" else None)
            if type(value) is not int or value < 0:
                raise ValueError("invalid quota usage")
            total += value
    if total >= TOKEN_STOP:
        raise RuntimeError("combined subscription token stop reached")
    return total


def prepare(out: Path, source_path: Path) -> None:
    if not out.is_relative_to(ROOT / "runs") or out == ROOT / "runs":
        raise ValueError("output must be beneath runs")
    source = read(source_path)
    validate_source(source)
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
    paths = [
        Path(__file__),
        HERE / "prose_codex.py",
        HERE / "prose_paragraph_revision.py",
        REGISTRATION,
        REGISTRATION.with_name("RUNBOOK.md"),
        source_path,
        source_path.with_name("source-review.md"),
        Path(prefix[1]),
    ]
    write_new(
        out / "manifest.json",
        {
            "source": source,
            "prefix": prefix,
            "order": ORDER,
            "files": {str(p): sha(p) for p in paths},
            "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "cli_version": subprocess.check_output([*prefix, "--version"], text=True).strip(),
            "authentication": "chatgpt",
            "token_stop": TOKEN_STOP,
            "call_limit": CALL_LIMIT,
            "disclosure_system": DISCLOSURE_SYSTEM,
        },
    )


def invoke(out: Path, relative: Path, name: str, request: dict[str, str], effort: str) -> Any:
    manifest = CODEX["validate"](out)
    directory = out / "calls" / relative
    if directory.exists():
        if (directory / "system.txt").read_text(encoding="utf-8") != request["system"]:
            raise ValueError("system identity changed")
    else:
        directory.mkdir(parents=True, exist_ok=False)
        (directory / "work").mkdir()
        (directory / "system.txt").write_text(request["system"], encoding="utf-8", newline="\n")
    if not (directory / f"{name}.request.json").exists():
        quota(out)
        if len(list(out.glob("calls/**/*.request.json"))) >= CALL_LIMIT:
            raise RuntimeError("sixteen-invocation limit reached")
    print(f"CELL {relative.as_posix()}, effort={effort}", flush=True)
    return CODEX["complete_once"](
        directory,
        name,
        {"prefix": manifest["prefix"], "requests": {name.split("-")[0]: request}},
        effort=effort,
    )


def inspect(out: Path, label: str, texts: list[str], expected: list[str], spans: list[str]) -> None:
    directory = out / "assembled"
    directory.mkdir(exist_ok=True)
    text = "\n\n".join(t.strip() for t in texts)
    text_path = directory / f"{label}.txt"
    if text_path.exists() and text_path.read_text(encoding="utf-8") != text + "\n":
        raise ValueError("assembled output changed")
    text_path.write_text(text + "\n", encoding="utf-8", newline="\n")
    actual = PATCH["literal_sequence"](text, spans)
    payload = {
        "literal_sequence_matches": actual == expected,
        "expected_literal_occurrences": len(expected),
        "actual_literal_occurrences": len(actual),
        "text_sha256": sha(text_path),
        "semantic_status": "unassessed; literal checks are not meaning",
    }
    path = directory / f"{label}.inspection.json"
    if path.exists():
        if read(path) != payload:
            raise ValueError("inspection changed")
    else:
        write_new(path, payload)


def run(out: Path, experiment: str) -> None:
    manifest = CODEX["validate"](out)
    source = manifest["source"]
    validate_source(source)
    original = source["original"]
    expected = PATCH["literal_sequence"](original["text"], original["verbatim"])
    for name in ORDER:
        if experiment == "reasoning":
            r = invoke(
                out,
                Path(experiment) / name,
                name,
                source["reasoning_request"],
                "high" if name.startswith("full") else "low",
            )
            inspect(out, f"reasoning-{name}", [r["text"]], expected, original["verbatim"])
        else:
            texts: list[str] = []
            for stage in range(1, 4):
                request = disclosure_request(
                    source, name.split("-")[0], stage, "\n\n".join(t.strip() for t in texts)
                )
                r = invoke(out, Path(experiment) / name / f"part-{stage}", name, request, "high")
                texts.append(r["text"])
                part_expected = source["parts"][stage - 1]["literals"]
                inspect(
                    out,
                    f"disclosure-{name}-part-{stage}",
                    [r["text"]],
                    part_expected,
                    original["verbatim"],
                )
            inspect(out, f"disclosure-{name}", texts, expected, original["verbatim"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "reasoning", "disclosure"))
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    if args.phase == "prepare":
        if not args.source:
            parser.error("prepare requires --source")
        prepare(args.out.resolve(), args.source.resolve())
    else:
        run(args.out.resolve(), args.phase)


if __name__ == "__main__":
    main()
