"""Event-activated attention states with matched writer exposure; research only."""

from __future__ import annotations

import argparse
import json
import runpy
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
OLD = runpy.run_path(str(HERE / "prose_attention.py"))
CODEX = OLD["CODEX"]
NARR = OLD["BASE"]["BASE"]
read, write_new, sha = (CODEX[k] for k in ("read", "write_new", "sha"))
REG = HERE / "prose-attention-events"
ORDER = ("initial-1", "updates-1", "background-1", "operative-1", "operative-2", "background-2")
TOKEN_STOP = 125_000
STATE_SCHEMA = """A state is {"concern":"1-30 words","foreground":["source ID"],
"peripheral":["source ID"],"basis":["source ID"],"unresolved":"1-20 words"}.
Use 1-3 foreground IDs, 0-3 peripheral IDs and 1-5 basis IDs, with no duplicates or
foreground/peripheral overlap. Every reference and every claim must be available at activation.
Concern is a provisional immediate preoccupation compatible with the source, not a new fact
or a summary of later events. Foreground/peripheral describe emphasis, not omitted events.
Infer no biography, identities, new mechanics, diagnosis, symbols or moral lesson. An open
question may stay uncertain. Do not supply narration, dialogue, ratings or prose advice."""
INITIAL_SYSTEM = (
    """Derive the protagonist's attention at this opening moment using only the
supplied known facts. No later story is supplied. Return only a state JSON object.
"""
    + STATE_SCHEMA
)
UPDATES_SYSTEM = (
    """Propose attention states activated AFTER the supplied source units have
fully occurred. Return only {"updates":[{"after":"activation ID","state":STATE}]} with one
entry for each activation_id in its given order. The initial state is already fixed.
The state before each activation is the previous returned state (initial before the first);
code supplies that relationship. Do not rewrite a before state to include the incoming event.
Each new state becomes available only after its complete source unit, never during an earlier
part of that unit. Its evidence pool is the initial_ids plus the source prefix through that
activation. Later source may not appear in a state's concerns, assumptions or questions as
established knowledge. Uncertainty and hypotheses must remain compatible with knowledge timing.
Follow the specific details the protagonist is occupied with as events arrive. A concern can
persist; every activation need not invent a new dramatic turn. Preserve all source truths.
"""
    + STATE_SCHEMA
)
WRITER_SYSTEM = """Write the complete opening chapter as novel prose in close third person,
past tense. Aim for 1500-1800 words. Return only the chapter, without title or commentary.
All source_units remain true at their specified times. Preserve events, causal relations,
quantities, scene division, viewpoint knowledge and ending. The required_narration IDs must
reach the reader through action, dialogue or narration; other facts may remain implicit.
Showing an event does not require explaining it afterward. Paragraph organization, gestures
and immediate dialogue are yours. Do not add incidents, biography, identities, powers or rules.
Preserve the display messages and their occurrence order, with punctuation fitting placement.
The attention_trajectory is provisional source-based understanding, not new canon or required
exposition. S0 is available at opening. Each later state activates only AFTER its named source
unit is complete. Before that, the preceding state applies. Transitions identify that preceding
state, the incoming source unit and the newly available state. Later states must not shape
earlier attention. Required events and knowledge timing remain authoritative throughout.
The rendering_mode specifies how to use this shared trajectory. Its states are not paragraphs
or required section breaks. No ban on interpretation or prescribed rhetorical style is added."""
MODES = {
    "background": """Treat the states as available background understanding at their valid
times. Compose with your ordinary choices of focus, emphasis, duration and transitions.
Foreground/peripheral distinctions are available interpretations, not directions governing
those narrative choices.""",
    "operative": """Use each currently available state to guide narrative focus, emphasis,
duration and transitions. Attend to foreground details through what occupies the character;
give peripheral facts the space their causal role needs. Let the incoming event meet the
preceding concern before the new state takes effect. Realize changes through what the prose
dwells on and moves toward; the state labels and concern sentences need not be explained.
Unresolved attention may remain open when events demand the next action. Preserve every
required event; do not make the character ignore a required perception or remain artificially
fixed on a concern when the supplied action demands an immediate response.""",
}


def reference_list(value: Any, pool: list[str], minimum: int, maximum: int) -> None:
    if (
        not isinstance(value, list)
        or not minimum <= len(value) <= maximum
        or any(not isinstance(i, str) or i not in pool for i in value)
        or len(set(value)) != len(value)
    ):
        raise ValueError("invalid or unavailable source reference")


def payload(source: Any) -> dict[str, Any]:
    if not isinstance(source, dict) or set(source) != {
        "chapter_source",
        "initial_ids",
        "activation_ids",
    }:
        raise ValueError("invalid attention-event source")
    common = json.loads(
        NARR["compose"](source["chapter_source"])["focused"]["prompt"].split("\n", 1)[1]
    )
    ids = [u["id"] for u in common["source_units"]]
    reference_list(source["initial_ids"], ids, 1, len(ids))
    reference_list(source["activation_ids"], ids, 1, len(ids))
    if source["activation_ids"] != sorted(source["activation_ids"], key=ids.index):
        raise ValueError("activation order changed")
    if set(source["initial_ids"]) & set(source["activation_ids"]):
        raise ValueError("initial facts cannot be new activations")
    common["display_templates"] = [s.rstrip("., ") for s in common.pop("literal_sequence")]
    return common


def available(source: Any, after: str | None) -> list[str]:
    ids = [u["id"] for u in payload(source)["source_units"]]
    known = set(source["initial_ids"])
    if after is not None:
        if after not in source["activation_ids"]:
            raise ValueError("unknown activation")
        known.update(ids[: ids.index(after) + 1])
    return [i for i in ids if i in known]


def validate_state(state: Any, pool: list[str]) -> None:
    if not isinstance(state, dict) or set(state) != {
        "concern",
        "foreground",
        "peripheral",
        "basis",
        "unresolved",
    }:
        raise ValueError("invalid attention state")
    for key, limit in (("concern", 30), ("unresolved", 20)):
        value = state[key]
        if not isinstance(value, str) or not 1 <= len(value.split()) <= limit:
            raise ValueError("invalid state text length")
    for key, minimum, maximum in (("foreground", 1, 3), ("peripheral", 0, 3), ("basis", 1, 5)):
        reference_list(state[key], pool, minimum, maximum)
    if set(state["foreground"]) & set(state["peripheral"]):
        raise ValueError("foreground/peripheral overlap")


def initial_request(source: Any) -> dict[str, str]:
    common = payload(source)
    known = [u for u in common["source_units"] if u["id"] in source["initial_ids"]]
    return {
        "system": INITIAL_SYSTEM,
        "prompt": json.dumps({"known_facts": known}, ensure_ascii=False),
    }


def updates_request(source: Any, initial: Any) -> dict[str, str]:
    validate_state(initial, available(source, None))
    return {
        "system": UPDATES_SYSTEM,
        "prompt": json.dumps(
            {
                **payload(source),
                "initial_ids": source["initial_ids"],
                "activation_ids": source["activation_ids"],
                "initial_state": initial,
                "allowed_ids_after": {i: available(source, i) for i in source["activation_ids"]},
            },
            ensure_ascii=False,
        ),
    }


def trajectory(source: Any, initial: Any, updates: Any) -> dict[str, Any]:
    validate_state(initial, available(source, None))
    if (
        not isinstance(updates, dict)
        or set(updates) != {"updates"}
        or not isinstance(updates["updates"], list)
        or len(updates["updates"]) != len(source["activation_ids"])
    ):
        raise ValueError("invalid update coverage")
    states = [{"id": "S0", "active_after": "opening", "state": initial}]
    transitions = []
    for index, (activation, row) in enumerate(
        zip(source["activation_ids"], updates["updates"], strict=True), 1
    ):
        if (
            not isinstance(row, dict)
            or set(row) != {"after", "state"}
            or row["after"] != activation
        ):
            raise ValueError("update activation changed")
        validate_state(row["state"], available(source, activation))
        states.append({"id": f"S{index}", "active_after": activation, "state": row["state"]})
        transitions.append(
            {
                "before_state": f"S{index - 1}",
                "incoming_source": activation,
                "after_state": f"S{index}",
            }
        )
    return {"states": states, "transitions": transitions}


def writer_requests(source: Any, initial: Any, updates: Any) -> dict[str, Any]:
    shared = {**payload(source), "attention_trajectory": trajectory(source, initial, updates)}
    return {
        mode: {
            "system": WRITER_SYSTEM,
            "prompt": json.dumps({**shared, "rendering_mode": text}, ensure_ascii=False),
        }
        for mode, text in MODES.items()
    }


def quota(out: Path) -> int:
    requests = list(out.glob("*/full-1.request.json"))
    if len(requests) > len(ORDER) or any(p.parent.name not in ORDER for p in requests):
        raise ValueError("unregistered invocation")
    total = 0
    for path in out.glob("*/full-1.result.json"):
        result = read(path)
        if path.parent.name not in ORDER or result["status"] != "completed":
            raise RuntimeError("previous failure; no retry")
        for key in ("input_tokens", "output_tokens", "reasoning_output_tokens"):
            value = result["usage"].get(key, 0 if key == "reasoning_output_tokens" else None)
            if type(value) is not int or value < 0:
                raise ValueError("invalid usage")
            total += value
    if total >= TOKEN_STOP:
        raise RuntimeError("subscription token stop reached")
    return total


def call(out: Path, name: str, request: Any, manifest: Any) -> dict[str, Any]:
    quota(out)
    if name not in ORDER:
        raise ValueError("unregistered invocation")
    print(f"LOGICAL CALL {name}", flush=True)
    return CODEX["complete_once"](
        out / name, "full-1", {"prefix": manifest["prefix"], "requests": {"full": request}}
    )


def artifact_files(out: Path, names: tuple[str, ...]) -> list[Path]:
    return [
        out / name / f"full-1.{suffix}"
        for name in names
        for suffix in ("request.json", "raw.json", "result.json", "txt")
    ]


def verify_files(value: dict[str, Any]) -> None:
    if any(sha(Path(p)) != h for p, h in value["files"].items()):
        raise ValueError("frozen intermediate changed")


def prepare(out: Path, source_path: Path) -> None:
    if not out.is_relative_to(ROOT / "runs") or out == ROOT / "runs":
        raise ValueError("output must be beneath runs")
    source = read(source_path)
    request = initial_request(source)
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
        text = (
            INITIAL_SYSTEM
            if name == "initial-1"
            else UPDATES_SYSTEM
            if name == "updates-1"
            else WRITER_SYSTEM
        )
        system.write_text(text, encoding="utf-8", newline="\n")
        systems.append(system)
    files = [
        Path(__file__),
        *[
            HERE / p
            for p in (
                "prose_attention.py",
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
            "initial_request": request,
            "prefix": prefix,
            "order": ORDER,
            "token_stop": TOKEN_STOP,
            "files": {str(p): sha(p) for p in files},
            "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "cli_version": subprocess.check_output([*prefix, "--version"], text=True).strip(),
            "authentication": "chatgpt",
        },
    )


def initial_phase(out: Path) -> None:
    m = CODEX["validate"](out)
    if m["initial_request"] != initial_request(m["source"]):
        raise ValueError("initial request changed")
    result = call(out, "initial-1", m["initial_request"], m)
    validate_state(json.loads(result["text"]), available(m["source"], None))


def updates_phase(out: Path) -> None:
    m = CODEX["validate"](out)
    initial = json.loads(read(out / "initial-1/full-1.result.json")["text"])
    bundle = {
        "initial": initial,
        "request": updates_request(m["source"], initial),
        "files": {str(p): sha(p) for p in artifact_files(out, ("initial-1",))},
    }
    path = out / "updates-manifest.json"
    if path.exists():
        if read(path) != bundle:
            raise ValueError("updates request changed")
    else:
        write_new(path, bundle)
    result = call(out, "updates-1", bundle["request"], m)
    trajectory(m["source"], initial, json.loads(result["text"]))


def freeze(out: Path, review_path: Path) -> None:
    m = CODEX["validate"](out)
    u = read(out / "updates-manifest.json")
    verify_files(u)
    updates = json.loads(read(out / "updates-1/full-1.result.json")["text"])
    review = read(review_path)
    names = ("initial-1", "updates-1")
    if (
        review.get("text_sha256") != {n: sha(out / n / "full-1.txt") for n in names}
        or any(
            review.get(k) is not True
            for k in ("source_compatible", "knowledge_timing", "no_new_canon")
        )
        or review.get("reviewed_activations") != ["opening", *m["source"]["activation_ids"]]
    ):
        raise ValueError("complete temporal review required")
    files = [*artifact_files(out, names), out / "updates-manifest.json", review_path]
    write_new(
        out / "draft-manifest.json",
        {
            "initial": u["initial"],
            "updates": updates,
            "requests": writer_requests(m["source"], u["initial"], updates),
            "trajectory": trajectory(m["source"], u["initial"], updates),
            "review": review,
            "files": {str(p): sha(p) for p in files},
        },
    )


def drafts(out: Path) -> None:
    for name in ORDER[2:]:
        m = CODEX["validate"](out)
        d = read(out / "draft-manifest.json")
        verify_files(d)
        if d["requests"] != writer_requests(m["source"], d["initial"], d["updates"]):
            raise ValueError("writer requests changed")
        call(out, name, d["requests"][name.rsplit("-", 1)[0]], m)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "initial", "updates", "freeze", "draft"))
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--review", type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    if args.phase == "prepare":
        if not args.source:
            parser.error("prepare requires --source")
        prepare(out, args.source.resolve())
    elif args.phase == "freeze":
        if not args.review:
            parser.error("freeze requires --review")
        freeze(out, args.review.resolve())
    else:
        {"initial": initial_phase, "updates": updates_phase, "draft": drafts}[args.phase](out)


if __name__ == "__main__":
    main()
