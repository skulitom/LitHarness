"""Frozen source-boundary, scene, language and subscription-writer diagnostics."""

from __future__ import annotations

import argparse
import json
import os
import runpy
import subprocess
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
BASE = runpy.run_path(str(HERE / "prose_narration_obligations.py"))
CODEX = BASE["CODEX"]
read, write_new, sha = (CODEX[k] for k in ("read", "write_new", "sha"))
REG = HERE / "prose-editor-boundary"
TOKEN_STOP = 300_000
CLAUDE_MODEL = "claude-opus-5"
CLAUDE = Path.home() / ".local/bin/claude.exe"
ORDER = (
    "selector",
    "codex-full-1",
    "claude-full-1",
    "codex-static-1",
    "claude-static-1",
    "codex-editor-1",
    "codex-editor-2",
    "codex-static-2",
    "claude-static-2",
    "codex-full-2",
    "claude-full-2",
    "mechanical-1",
    "social-1",
    "social-2",
    "mechanical-2",
    "russian-source-1",
    "russian-render-1",
    "english-source-1",
    "english-render-1",
    "english-source-2",
    "english-render-2",
    "russian-source-2",
    "russian-render-2",
)
SELECTOR_SYSTEM = """You prepare source material for a novelist. Select which optional units
the writer needs to render a causally intelligible chapter, keeping useful interiority but
avoiding obligatory recaps of information already carried by action. Mandatory units cannot
be removed. You may only KEEP or DROP each optional unit; do not rewrite any source, invent
facts, propose a plot, draft prose, evaluate a candidate or set a word target. Return only a
JSON object with key decisions: an array containing exactly one object per optional unit,
with keys id, keep (boolean), reason (short string). Reasons are audit material and will not
reach the writer. Keeping all or none of the optional units is permitted."""
SCENE_SYSTEM = """Write the opening scene of a novel in close third person, past tense,
through the supplied viewpoint character. Follow the supplied facts, motives and endpoint.
Invent the dialogue and immediate interaction needed to connect them, without new characters,
backstory, rules, side incidents or a later scene. The source is not a paragraph outline.
There is no word target, required comparison, prescribed first sentence or tell blacklist.
Return only the scene prose, without a title, commentary, analysis or score."""
RENDER_SYSTEM = """Render the supplied passage into English novel prose, in close third
person and past tense. If it is already English, rewrite it into English under the same
requirements. Preserve its events, meanings, knowledge timing, motives, point of view and
endpoint. Preserve the protected literal occurrences exactly and in order, even if they look
awkward. Do not add facts, explanations or imagery to fill perceived gaps. Do not consult an
outside story source. Return only the complete English passage, without commentary or a title."""


def package(source: dict[str, Any], keep: list[str]) -> dict[str, Any]:
    """Filter actual source bytes; original prose and editor reasons never reach drafting."""
    request = BASE["compose"](source)["focused"]
    payload = json.loads(request["prompt"].split("\n", 1)[1])
    mandatory = payload["required_narration"]
    ids = [f["id"] for f in source["facts"]]
    if len(set(keep)) != len(keep) or not set(mandatory) <= set(keep) <= set(ids):
        raise ValueError("selection loses mandatory facts or contains invalid IDs")
    if not set(source["scene_break_after"]) <= set(mandatory):
        raise ValueError("scene break must refer to a mandatory unit")
    payload["source_units"] = [f for f in source["facts"] if f["id"] in keep]
    return {
        "system": request["system"],
        "prompt": "Story source and narration assignment:\n"
        + json.dumps(payload, ensure_ascii=False),
    }


def selected_ids(source: dict[str, Any], text: str) -> list[str]:
    value = json.loads(text)
    if not isinstance(value, dict) or set(value) != {"decisions"}:
        raise ValueError("selector must return only decisions")
    rows = value["decisions"]
    if not isinstance(rows, list) or any(
        not isinstance(r, dict)
        or set(r) != {"id", "keep", "reason"}
        or not isinstance(r["id"], str)
        or type(r["keep"]) is not bool
        or not isinstance(r["reason"], str)
        or not r["reason"].strip()
        for r in rows
    ):
        raise ValueError("malformed selector decision")
    optional = source["implicit_ids"]
    if len(rows) != len(optional) or {r["id"] for r in rows} != set(optional):
        raise ValueError("selector must cover each optional ID exactly once")
    dropped = {r["id"] for r in rows if not r["keep"]}
    return [f["id"] for f in source["facts"] if f["id"] not in dropped]


def request_for(name: str, source: dict[str, Any], prior: dict[str, Any]) -> dict[str, str]:
    if name not in ORDER:
        raise ValueError("unregistered call")
    chapter = source["chapter_source"]
    all_ids = [f["id"] for f in chapter["facts"]]
    mandatory = [i for i in all_ids if i not in chapter["implicit_ids"]]
    provider = "claude" if name.startswith("claude-") else "codex"
    if name == "selector":
        request = {
            "system": SELECTOR_SYSTEM,
            "prompt": json.dumps(
                {
                    "source": json.loads(package(chapter, all_ids)["prompt"].split("\n", 1)[1]),
                    "optional_ids": chapter["implicit_ids"],
                },
                ensure_ascii=False,
            ),
        }
    elif name.startswith(("codex-", "claude-")):
        condition = name.split("-")[1]
        keep = (
            all_ids
            if condition == "full"
            else mandatory
            if condition == "static"
            else selected_ids(chapter, prior["selector"]["text"])
        )
        request = package(chapter, keep)
    elif name.startswith(("mechanical-", "social-")):
        request = {
            "system": SCENE_SYSTEM,
            "prompt": json.dumps(source["scenes"][name.split("-")[0]], ensure_ascii=False),
        }
    elif "-source-" in name:
        request = package(chapter, mandatory)
        language = "Russian" if name.startswith("russian-") else "English"
        request["system"] += (
            f"\nWrite the ordinary narration and dialogue in {language}. "
            "Keep all protected literal spans in their supplied English."
        )
    else:
        parent = name.replace("-render-", "-source-")
        literals = json.loads(package(chapter, mandatory)["prompt"].split("\n", 1)[1])[
            "literal_sequence"
        ]
        request = {
            "system": RENDER_SYSTEM,
            "prompt": json.dumps(
                {
                    "passage": prior[parent]["text"],
                    "protected_literal_sequence": literals,
                },
                ensure_ascii=False,
            ),
        }
    return {"provider": provider, **request}


def claude_env() -> dict[str, str]:
    # Keep subscription auth; remove direct-billing and alternate-provider routes.
    return {
        k: v
        for k, v in CODEX["subscription_env"]().items()
        if not k.upper().startswith(("ANTHROPIC_", "CLAUDE_CODE_USE_"))
        and k.upper() not in {"CLAUDE_API_KEY", "CLAUDE_CODE_API_KEY"}
    }


def claude_argv(binary: str, system: Path) -> list[str]:
    return [
        binary,
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--model",
        CLAUDE_MODEL,
        "--effort",
        "high",
        "--safe-mode",
        "--strict-mcp-config",
        "--mcp-config",
        '{"mcpServers":{}}',
        "--no-session-persistence",
        "--permission-mode",
        "manual",
        "--tools",
        "",
        "--allowed-tools",
        "",
        "--max-turns",
        "1",
        "--system-prompt-file",
        str(system),
    ]


def parse_claude(stdout: str) -> dict[str, Any]:
    events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    results = [e for e in events if e.get("type") == "result"]
    if len(results) != 1:
        raise ValueError("expected exactly one Claude result")
    result = results[0]
    if result.get("is_error") or result.get("subtype") != "success":
        raise ValueError("Claude result failed")
    if result.get("num_turns") != 1 or result.get("permission_denials"):
        raise ValueError("unexpected Claude turn or permission activity")
    for event in events:
        if event.get("type") == "assistant":
            blocks = event.get("message", {}).get("content", [])
            if any(b.get("type") not in {"text", "thinking", "redacted_thinking"} for b in blocks):
                raise ValueError("unexpected Claude tool activity")
    text = result.get("result")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("missing Claude prose")
    raw_usage = result.get("usage", {})
    keys = (
        "input_tokens",
        "cache_read_input_tokens",
        "cache_creation_input_tokens",
        "output_tokens",
    )
    if any(type(raw_usage.get(k)) is not int or raw_usage[k] < 0 for k in keys):
        raise ValueError("missing Claude usage")
    models = list(result.get("modelUsage", {}))
    if models != [CLAUDE_MODEL]:
        raise ValueError("unexpected or missing resolved Claude model")
    return {
        "text": text,
        "usage": {
            "input_tokens": sum(raw_usage[k] for k in keys[:3]),
            "cached_input_tokens": raw_usage["cache_read_input_tokens"],
            "output_tokens": raw_usage["output_tokens"],
        },
        "raw_usage": raw_usage,
        "resolved_model": models[0],
        "reported_equivalent_cost_usd": result.get("total_cost_usd"),
        "event_types": [e["type"] for e in events],
    }


def quota(results: list[dict[str, Any]]) -> int:
    if any(r.get("status") != "completed" for r in results):
        raise RuntimeError("prior failure or unknown usage; no further dispatch")
    total = sum(
        r["usage"]["input_tokens"]
        + r["usage"]["output_tokens"]
        + r["usage"].get("reasoning_output_tokens", 0)
        for r in results
    )
    if total >= TOKEN_STOP:
        raise RuntimeError("combined token dispatch stop reached")
    return total


def prepare(out: Path, source_path: Path) -> None:
    if not out.is_relative_to(ROOT / "runs") or out == ROOT / "runs":
        raise ValueError("output must be beneath runs")
    source = read(source_path)
    for name in ORDER:
        if "editor" not in name and "render" not in name:
            request_for(name, source, {})
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
        raise RuntimeError("ChatGPT subscription login required")
    auth_c = subprocess.run(
        [str(CLAUDE), "auth", "status"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=claude_env(),
        check=False,
    )
    ca = json.loads(auth_c.stdout)
    if (
        auth_c.returncode
        or not ca.get("loggedIn")
        or ca.get("authMethod") != "claude.ai"
        or ca.get("apiProvider") != "firstParty"
        or ca.get("subscriptionType") != "max"
    ):
        raise RuntimeError("Claude Max subscription login required")
    out.mkdir(parents=True, exist_ok=False)
    paths = [
        Path(__file__),
        HERE / "prose_narration_obligations.py",
        HERE / "prose_protected_reconstruction.py",
        HERE / "prose_paragraph_revision.py",
        HERE / "prose_codex.py",
        REG / "PREREG.md",
        REG / "RUNBOOK.md",
        source_path,
        source_path.with_name("source-review.md"),
        source_path.with_name("prepare_source.py"),
        Path(prefix[1]),
        CLAUDE,
    ]
    write_new(
        out / "manifest.json",
        {
            "source": source,
            "prefix": prefix,
            "claude_binary": str(CLAUDE),
            "order": list(ORDER),
            "files": {str(p): sha(p) for p in paths},
            "token_stop": TOKEN_STOP,
            "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "versions": {
                "codex": subprocess.check_output([*prefix, "--version"], text=True).strip(),
                "claude": subprocess.check_output([str(CLAUDE), "--version"], text=True).strip(),
            },
            "authentication": {"codex": "chatgpt", "claude": "claude.ai/max/firstParty"},
        },
    )


def complete(
    out: Path, name: str, manifest: dict[str, Any], prior: dict[str, Any]
) -> dict[str, Any]:
    folder = out / name
    folder.mkdir(exist_ok=True)
    (folder / "work").mkdir(exist_ok=True)
    request = request_for(name, manifest["source"], prior)
    system = folder / "system.txt"
    if system.exists():
        if system.read_text(encoding="utf-8") != request["system"]:
            raise ValueError("system identity changed")
    else:
        system.write_text(request["system"], encoding="utf-8", newline="\n")
    provider = request["provider"]
    arguments = (
        CODEX["argv"](manifest["prefix"], system, folder / "work")
        if provider == "codex"
        else claude_argv(manifest["claude_binary"], system)
    )
    frozen = {
        **request,
        "argv": arguments,
        "effort": "high",
        "authentication": manifest["authentication"][provider],
        "requested_model": CODEX["MODEL"] if provider == "codex" else CLAUDE_MODEL,
    }
    qpath, rpath = folder / "request.json", folder / "result.json"
    if qpath.exists():
        if read(qpath) != frozen:
            raise ValueError("request identity changed")
        if not rpath.exists() or read(rpath)["status"] != "completed":
            raise RuntimeError("interrupted or failed call; no retry")
        return read(rpath)
    if os.environ.get("LITHARNESS_ENV") == "test":
        raise RuntimeError("live trial disabled in tests")
    quota(list(prior.values()))
    if len(list(out.glob("*/request.json"))) >= len(ORDER):
        raise RuntimeError("invocation limit reached")
    write_new(qpath, frozen)
    print(f"START {name}", flush=True)
    started = time.monotonic()
    try:
        proc = subprocess.run(
            arguments,
            input=request["prompt"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=folder / "work",
            env=CODEX["subscription_env"]() if provider == "codex" else claude_env(),
            timeout=900,
            check=False,
        )
        write_new(
            folder / "raw.json",
            {"stdout": proc.stdout, "stderr": proc.stderr, "exit_code": proc.returncode},
        )
        if proc.returncode:
            raise RuntimeError(f"CLI exit {proc.returncode}; retained raw response")
        parsed = (
            CODEX["parse_events"](proc.stdout) if provider == "codex" else parse_claude(proc.stdout)
        )
        result = {"status": "completed", **parsed}
    except Exception as error:
        if isinstance(error, subprocess.TimeoutExpired):
            write_new(
                folder / "raw.json",
                {
                    k: (
                        v.decode("utf-8", errors="replace")
                        if isinstance(v := getattr(error, k), bytes)
                        else v
                    )
                    for k in ("stdout", "stderr")
                },
            )
        result = {"status": "failed", "error_type": type(error).__name__, "error": str(error)}
    result["wall_ms"] = round(1000 * (time.monotonic() - started))
    write_new(rpath, result)
    if result["status"] != "completed":
        raise RuntimeError(f"{name} failed; retained, no retry")
    (folder / "prose.txt").write_text(result["text"] + "\n", encoding="utf-8", newline="\n")
    print(f"DONE {name}: {result['wall_ms'] / 1000:.1f}s, {result['usage']}", flush=True)
    return result


def run(out: Path, until: str | None) -> None:
    prior: dict[str, Any] = {}
    for name in ORDER:
        manifest = CODEX["validate"](out)
        if "editor" in name:
            try:
                selected_ids(manifest["source"]["chapter_source"], prior["selector"]["text"])
            except (ValueError, TypeError):
                path = out / f"{name}.skipped.json"
                if not path.exists():
                    write_new(path, {"reason": "invalid selector payload; no repair or redraw"})
                continue
        prior[name] = complete(out, name, manifest, prior)
        if name == until:
            break


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "run"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--until", choices=ORDER)
    args = parser.parse_args()
    if args.phase == "prepare":
        if not args.source:
            parser.error("prepare requires --source")
        prepare(args.out.resolve(), args.source.resolve())
    else:
        run(args.out.resolve(), args.until)


if __name__ == "__main__":
    main()
