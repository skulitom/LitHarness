"""One persistent concern versus fresh source-only chapters; research only."""

from __future__ import annotations

import argparse
import json
import runpy
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
T = runpy.run_path(str(HERE / "prose_attention_events.py"))
CODEX = T["CODEX"]
read, write_new, sha = (T[k] for k in ("read", "write_new", "sha"))
REG = HERE / "prose-persistent-concern"
ORDER = ("concern-1", "source-1", "persistent-1", "persistent-2", "source-2")
TOKEN_STOP = 105_000
CONCERN_SYSTEM = """Derive ONE practical, unresolved concern of the protagonist from the
source. It must plausibly survive several events, become background while urgent action takes
over, and regain attention when later source evidence bears on it. Do not invent a story,
biography, motive, answer, rule or moral lesson. Its question may use only knowledge available
at opens_after. All source is visible to you for planning; later knowledge cannot be assumed
in the earlier question. Choose activation points from allowed_ids_after, never source groups
or already-known context units. The source_units.id field is the reference namespace.
Return only JSON with exactly these keys:
{"question":"1-30 words", "opens_after":"opening or source_units.id", "basis":["id"],
 "checkpoints":[{"after":"id", "mode":"foreground|background|release", "notice":["id"]}]}.
Use 1-5 basis IDs available at opens_after. Use 3-5 strictly ordered checkpoints AFTER opening
the concern. Include background and a later foreground checkpoint; the last foreground must
be at least three source-unit positions after opening. Initial mode is foreground. The same
question persists; do not create a fresh question or a summary at each event. A foreground
checkpoint names 1-2 source particulars in notice; background/release use an empty notice list.
Notice IDs must already be available after that checkpoint. They are remembered/observed
particulars, not permission to move their source events. Background suspends emphasis without
answering the question. Optional release must be the last checkpoint; it releases attention,
not necessarily resolves the uncertainty. Do not force a definitive answer or an end-of-chapter
lesson. The complete source unit occurs BEFORE its checkpoint takes effect. Basis and notice
may refer only to opening-known IDs plus source prefix through their respective activation.
Return no per-checkpoint explanation, prose, dialogue, ranking or quality verdict. If no such
concern fits the source, return {"unavailable":true} instead of inventing one."""
WRITER_SYSTEM = """Write the complete opening chapter as novel prose in close third person,
past tense. Aim for 1500-1800 words. Return only the chapter, without title or commentary.
All source_units remain true at their specified times. Preserve events, causal relations,
quantities, scene division, viewpoint knowledge and ending. The required_narration IDs must
reach the reader through action, dialogue or narration; other facts may remain implicit.
Showing an event does not require explaining it afterward. Paragraph organization, gestures
and immediate dialogue are yours. Do not add incidents, biography, identities, powers or rules.
Preserve display messages and their occurrence order, with punctuation fitting placement.
If concern_schedule is supplied, it is a provisional allocation of attention, not new canon,
required inner speech or a new motive for an established action. Use it only at its valid times.
The question begins AFTER opens_after is complete (or at opening) in foreground. It persists
unchanged across intervening events. Each checkpoint changes its mode only AFTER that entire
source unit. Background leaves it unattended while necessary action takes over; later
foreground can bring it back through available particulars in notice. Release ends its use
without asserting an answer. Notice references never move the original perception or event.
Use the concern to choose particulars, duration and returns of attention. There is no duty to
state its question, announce a checkpoint or explain what a return means. Handle all required
actions and interpretations at their source times, even while a concern remains unresolved.
No prescribed paragraph pattern, interpretation ban or additional narrative is requested."""


def payload(source: Any) -> dict[str, Any]:
    result = T["payload"](source)
    result["source_units"] = [
        {k: v for k, v in u.items() if k != "source_id"} for u in result["source_units"]
    ]
    return result


def available(source: Any, after: str) -> list[str]:
    ids = [u["id"] for u in payload(source)["source_units"]]
    if after != "opening" and after not in ids:
        raise ValueError("unknown activation")
    known = set(source["initial_ids"])
    if after != "opening":
        known.update(ids[: ids.index(after) + 1])
    return [i for i in ids if i in known]


def anchors(source: Any) -> list[str]:
    return [
        "opening",
        *[
            u["id"]
            for u in payload(source)["source_units"]
            if u["kind"] != "context" and u["id"] not in source["initial_ids"]
        ],
    ]


def validate_schedule(source: Any, value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {
        "question",
        "opens_after",
        "basis",
        "checkpoints",
    }:
        raise ValueError("no valid concern schedule")
    if not isinstance(value["question"], str) or not 1 <= len(value["question"].split()) <= 30:
        raise ValueError("invalid question length")
    ids = [u["id"] for u in payload(source)["source_units"]]
    if value["opens_after"] not in anchors(source):
        raise ValueError("opening must be an available event boundary")
    T["reference_list"](value["basis"], available(source, value["opens_after"]), 1, 5)
    start = -1 if value["opens_after"] == "opening" else ids.index(value["opens_after"])
    rows = value["checkpoints"]
    if not isinstance(rows, list) or not 3 <= len(rows) <= 5:
        raise ValueError("invalid checkpoint count")
    previous, background_seen, returned = start, False, False
    modes: dict[str, str] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {"after", "mode", "notice"}:
            raise ValueError("invalid checkpoint shape")
        if row["after"] not in anchors(source)[1:] or ids.index(row["after"]) <= previous:
            raise ValueError("checkpoint chronology changed")
        previous = ids.index(row["after"])
        mode = row["mode"]
        if mode not in ("foreground", "background", "release"):
            raise ValueError("unknown attention mode")
        if mode == "release" and index != len(rows) - 1:
            raise ValueError("release must be terminal")
        low, high = (1, 2) if mode == "foreground" else (0, 0)
        T["reference_list"](row["notice"], available(source, row["after"]), low, high)
        if mode == "background":
            background_seen = True
        elif mode == "foreground" and background_seen and previous - start >= 3:
            returned = True
        modes[row["after"]] = mode
    if not returned:
        raise ValueError("no persistent return after intervening events")
    # Each value applies AFTER its unit. No supplied before-state can overwrite history.
    timeline, active = {"opening": "foreground" if start == -1 else "unavailable"}, "unavailable"
    if start == -1:
        active = "foreground"
    for id in ids:
        if id == value["opens_after"]:
            active = "foreground"
        if id in modes:
            active = modes[id]
        timeline[id] = active
    return timeline


def concern_request(source: Any) -> dict[str, str]:
    p = payload(source)
    return {
        "system": CONCERN_SYSTEM,
        "prompt": json.dumps(
            {
                "source_units": p["source_units"],
                "initial_ids": source["initial_ids"],
                "allowed_ids_after": {i: available(source, i) for i in anchors(source)},
            },
            ensure_ascii=False,
        ),
    }


def writer_requests(source: Any, schedule: Any) -> dict[str, Any]:
    validate_schedule(source, schedule)
    common = payload(source)
    return {
        "source": {"system": WRITER_SYSTEM, "prompt": json.dumps(common, ensure_ascii=False)},
        "persistent": {
            "system": WRITER_SYSTEM,
            "prompt": json.dumps({**common, "concern_schedule": schedule}, ensure_ascii=False),
        },
    }


def quota(out: Path) -> int:
    requests = list(out.glob("*/full-1.request.json"))
    if len(requests) > len(ORDER) or any(p.parent.name not in ORDER for p in requests):
        raise ValueError("unregistered invocation")
    total = 0
    for path in out.glob("*/full-1.result.json"):
        r = read(path)
        if path.parent.name not in ORDER or r["status"] != "completed":
            raise RuntimeError("previous failure; no retry")
        for key in ("input_tokens", "output_tokens", "reasoning_output_tokens"):
            n = r["usage"].get(key, 0 if key == "reasoning_output_tokens" else None)
            if type(n) is not int or n < 0:
                raise ValueError("invalid usage")
            total += n
    if total >= TOKEN_STOP:
        raise RuntimeError("subscription token stop reached")
    return total


def call(out: Path, name: str, request: Any, m: Any) -> dict[str, Any]:
    quota(out)
    if name not in ORDER:
        raise ValueError("unregistered invocation")
    print(f"LOGICAL CALL {name}", flush=True)
    return CODEX["complete_once"](
        out / name, "full-1", {"prefix": m["prefix"], "requests": {"full": request}}
    )


def prepare(out: Path, source_path: Path) -> None:
    if not out.is_relative_to(ROOT / "runs") or out == ROOT / "runs":
        raise ValueError("output must be beneath runs")
    source = read(source_path)
    request = concern_request(source)
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
        path = folder / "system.txt"
        path.write_text(
            CONCERN_SYSTEM if name == "concern-1" else WRITER_SYSTEM, encoding="utf-8", newline="\n"
        )
        systems.append(path)
    files = [
        Path(__file__),
        *[
            HERE / p
            for p in (
                "prose_attention_events.py",
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
            "concern_request": request,
            "prefix": prefix,
            "order": ORDER,
            "token_stop": TOKEN_STOP,
            "files": {str(p): sha(p) for p in files},
            "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "cli_version": subprocess.check_output([*prefix, "--version"], text=True).strip(),
            "authentication": "chatgpt",
        },
    )


def derive(out: Path) -> None:
    m = CODEX["validate"](out)
    if m["concern_request"] != concern_request(m["source"]):
        raise ValueError("concern request changed")
    r = call(out, "concern-1", m["concern_request"], m)
    validate_schedule(m["source"], json.loads(r["text"]))


def freeze(out: Path, review_path: Path) -> None:
    m = CODEX["validate"](out)
    schedule = json.loads(read(out / "concern-1/full-1.result.json")["text"])
    timeline = validate_schedule(m["source"], schedule)
    review = read(review_path)
    if (
        review.get("text_sha256") != sha(out / "concern-1/full-1.txt")
        or review.get("reviewed_activations")
        != [schedule["opens_after"], *[r["after"] for r in schedule["checkpoints"]]]
        or any(
            review.get(k) is not True
            for k in ("source_compatible", "knowledge_timing", "no_new_canon")
        )
    ):
        raise ValueError("complete semantic review required")
    files = [*T["artifact_files"](out, ("concern-1",)), review_path]
    write_new(
        out / "draft-manifest.json",
        {
            "schedule": schedule,
            "timeline": timeline,
            "requests": writer_requests(m["source"], schedule),
            "review": review,
            "files": {str(p): sha(p) for p in files},
        },
    )


def draft(out: Path) -> None:
    for name in ORDER[1:]:
        m = CODEX["validate"](out)
        d = read(out / "draft-manifest.json")
        T["verify_files"](d)
        if d["requests"] != writer_requests(m["source"], d["schedule"]):
            raise ValueError("writer request changed")
        call(out, name, d["requests"][name.rsplit("-", 1)[0]], m)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "derive", "freeze", "draft"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--review", type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    if args.phase in ("prepare", "freeze"):
        path = args.source if args.phase == "prepare" else args.review
        if not path:
            parser.error("prepare requires --source; freeze requires --review")
        {"prepare": prepare, "freeze": freeze}[args.phase](out, path.resolve())
    else:
        {"derive": derive, "draft": draft}[args.phase](out)


if __name__ == "__main__":
    main()
