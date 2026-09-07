"""Six subscription-only drafts with nested ending and event constraints; research only."""

from __future__ import annotations

import argparse
import json
import runpy
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
BASE = runpy.run_path(str(HERE / "prose_narration_obligations.py"))
CODEX = BASE["CODEX"]
read, write_new, sha = (CODEX[k] for k in ("read", "write_new", "sha"))
REG = HERE / "prose-constraint-levels"
ORDER = ("premise-1", "ending-1", "sequence-1", "sequence-2", "ending-2", "premise-2")
TOKEN_STOP = 110_000
SYSTEM = """Write an opening chapter of a novel in close third person, past tense, following
the supplied protagonist. Aim for 1500-1800 words. Return only the chapter prose, without a
title, explanation of your work or score.
The common source describes the starting situation and world. Keep it true; facts available
to the writer are not automatically known to the character or required to be explained to
the reader. Choose actions, interactions, discoveries, attention and paragraph organization.
You may invent immediate dialogue, gestures and practical attempts consistent with this world.
Do not invent extra supernatural rules, powers, equipment or explanatory backstory.
If required_ending is supplied, reach and convey those end conditions by the chapter's end.
If event_sequence is supplied, also preserve every listed event, context and realization at
its specified time, including consequential quantities and causal relationships. Convey those
listed units through the prose, preserving their distinctions between observation and inference.
Otherwise, the course of events is yours. With no required ending, choose where this opening
chapter stops. Display templates govern wording when the corresponding message occurs; they
do not require occurrences. Punctuation may fit the message's placement in prose."""


def units(value: Any) -> None:
    if (
        not isinstance(value, list)
        or not value
        or any(
            not isinstance(u, dict)
            or set(u) != {"id", "text"}
            or any(not isinstance(v, str) or not v.strip() for v in u.values())
            for u in value
        )
        or len({u["id"] for u in value}) != len(value)
    ):
        raise ValueError("invalid source units")


def compose(source: Any) -> dict[str, Any]:
    if not isinstance(source, dict) or set(source) != {
        "chapter_source",
        "common",
        "required_ending",
        "ending_displays",
    }:
        raise ValueError("malformed constraint source")
    common = source["common"]
    if not isinstance(common, dict) or set(common) != {"units", "display_templates"}:
        raise ValueError("invalid common source")
    units(common["units"])
    units(source["required_ending"])
    for displays in (common["display_templates"], source["ending_displays"]):
        if (
            not isinstance(displays, dict)
            or not displays
            or any(not isinstance(v, str) or not v.strip() for v in displays.values())
            or any(not isinstance(k, str) or not k.strip() for k in displays)
        ):
            raise ValueError("invalid display templates")
    if set(common["display_templates"]) & set(source["ending_displays"]):
        raise ValueError("display template collision")
    detailed = json.loads(
        BASE["compose"](source["chapter_source"])["full"]["prompt"].split("\n", 1)[1]
    )
    payloads = {"premise": {"common": common}}
    payloads["ending"] = {
        **payloads["premise"],
        "required_ending": source["required_ending"],
        "ending_display_templates": source["ending_displays"],
    }
    payloads["sequence"] = {
        **payloads["ending"],
        "event_sequence": detailed["source_units"],
        "scene_break_after_unit": detailed["scene_break_after_unit"],
    }
    return {
        k: {"system": SYSTEM, "prompt": json.dumps(v, ensure_ascii=False)}
        for k, v in payloads.items()
    }


def quota(out: Path) -> int:
    total = 0
    for path in out.glob("*/full-1.result.json"):
        result = read(path)
        if result["status"] != "completed":
            raise RuntimeError("previous failure; no retry")
        for key in ("input_tokens", "output_tokens", "reasoning_output_tokens"):
            value = result["usage"].get(key, 0 if key == "reasoning_output_tokens" else None)
            if type(value) is not int or value < 0:
                raise ValueError("invalid quota usage")
            total += value
    if total >= TOKEN_STOP:
        raise RuntimeError("subscription token stop reached")
    return total


def prepare(out: Path, source_path: Path) -> None:
    if not out.is_relative_to(ROOT / "runs") or out == ROOT / "runs":
        raise ValueError("output must be beneath runs")
    source = read(source_path)
    requests = compose(source)
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
        system.write_text(SYSTEM, encoding="utf-8", newline="\n")
        systems.append(system)
    paths = [
        Path(__file__),
        HERE / "prose_narration_obligations.py",
        HERE / "prose_protected_reconstruction.py",
        HERE / "prose_paragraph_revision.py",
        HERE / "prose_codex.py",
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
            "requests": requests,
            "prefix": prefix,
            "order": ORDER,
            "files": {str(p): sha(p) for p in paths},
            "token_stop": TOKEN_STOP,
            "authentication": "chatgpt",
            "transport_slot_per_logical_call": "full-1",
            "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "cli_version": subprocess.check_output([*prefix, "--version"], text=True).strip(),
        },
    )


def run(out: Path) -> None:
    for name in ORDER:
        manifest = CODEX["validate"](out)
        if manifest["requests"] != compose(manifest["source"]):
            raise ValueError("frozen requests changed")
        existing = list(out.glob("*/full-1.request.json"))
        if any(p.parent.name not in ORDER for p in existing):
            raise ValueError("unregistered request folder")
        quota(out)
        folder = out / name
        if not (folder / "full-1.request.json").exists() and len(existing) >= len(ORDER):
            raise RuntimeError("six-invocation limit reached")
        print(f"LOGICAL CALL {name}", flush=True)
        CODEX["complete_once"](
            folder,
            "full-1",
            {
                "prefix": manifest["prefix"],
                "requests": {"full": manifest["requests"][name.rsplit("-", 1)[0]]},
            },
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "run"))
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    if args.phase == "prepare":
        if not args.source:
            parser.error("prepare requires --source")
        prepare(args.out.resolve(), args.source.resolve())
    else:
        run(args.out.resolve())


if __name__ == "__main__":
    main()
