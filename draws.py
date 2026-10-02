"""How often a pitch draw passes its hard checks, by brief and by agent, measured by code alone.

    python draws.py approve   yours to run: records the hash of this runner, the cases and the runtime; no call
    python draws.py run [--variant baseline] [--agent codex|claude[:model[:effort]]] [--reps 4] [--jobs 2]
                        [--timeout-s 300] [--only ID,ID]
    python draws.py report    recomputes every number from the stored rows and writes summary.md

A description, never a verdict: a passing bible cleared the money, leak and shape checks and nothing more, and
the operator's glance still decides. One row is one fresh pitch draw through serial.new, so a row costs one call.
Rows, traces and each draw's whole call folder live under $LITHARNESS_HOME/evals/pitch-draws/, outside the repo;
the cases and the protocol are in experiments/2026-10-02-pitch-draws/.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import contextlib
from functools import partial
import io
import json
import os
from pathlib import Path
import random
import re
import statistics
import sys
import threading
import time

from litharness import checks, files, serial, tells, transport

ROOT = Path(__file__).resolve().parent
CASES = ROOT / "experiments" / "2026-10-02-pitch-draws" / "cases.json"
METRICS = [{"id": "pass", "label": "passes", "kind": "binary"}, {"id": "money_clean", "label": "money clean", "kind": "binary"},
           {"id": "shape_ok", "label": "shape ok", "kind": "binary"}, {"id": "leak_clean", "label": "leak clean", "kind": "binary"}]
PERF = [{"id": "latency_s", "label": "seconds", "unit": "s"}, {"id": "tokens", "label": "tokens"},
        {"id": "words", "label": "words"}, {"id": "money_hits", "label": "money words"}, {"id": "admin_hits", "label": "admin words"}]
FAMILIES = {"money": "money_clean", "pitch-shape": "shape_ok", "leak": "leak_clean"}
STREAK = 4  # this many failed attempts in a row stop the run instead of spending the rest of it
BRIEFS = 5  # an interval is printed from this many briefs up


def harness() -> tuple[str, list[str]]:
    """One hash over this runner, the cases and the runtime: what a person approves before anything is spent."""
    paths = [Path(__file__).resolve(), CASES, *sorted((ROOT / "litharness").glob("*.py"))]
    names = [p.relative_to(ROOT).as_posix() if ROOT in p.parents else p.name for p in paths]
    return files.sha(b"".join(name.encode() + b"\0" + p.read_bytes() + b"\0" for name, p in zip(names, paths))), names


def load(path: Path) -> list[dict]:
    """The rows of a .jsonl file; a line torn by a crash is skipped."""
    found = []
    for line in files.read(path).splitlines() if path.is_file() else []:
        with contextlib.suppress(ValueError):
            found.append(json.loads(line))
    return found


def append(path: Path, row: dict) -> None:
    """One row, written as its draw completes, so a crash costs nothing already drawn."""
    path.parent.mkdir(parents=True, exist_ok=True)
    torn = path.is_file() and path.stat().st_size and not path.read_bytes().endswith(b"\n")
    with open(path, "ab") as handle:
        handle.write(b"\n" * torn + json.dumps(row, ensure_ascii=False).encode("utf-8") + b"\n")
        handle.flush()
        os.fsync(handle.fileno())


def cases(only: str | None = None) -> list[dict]:
    """The approved briefs. Each must be able to pass: one whose own words trip the money check is refused
    here, before anything is spent, because every draw on it would stop as located in our request."""
    found = [case for case in files.load(CASES)["cases"] if not only or case["id"] in only.split(",")]
    for case in found:
        if (not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,40}", case["id"]) or checks.money(case["brief"], "pitch")
                or not 0 < tells.words(case["brief"]) <= serial.BRIEF_WORDS):
            raise ValueError(f"case {case['id']!r}: a lowercase id, 1-{serial.BRIEF_WORDS} words, no money word of its own")
    if not found or len({case["id"] for case in found}) != len(found):
        raise ValueError("no case was chosen, or two cases share an id")
    return found


def graded(case: dict, rep: int, fails: list[str], folder: Path) -> tuple[dict, list[dict]]:
    """The row and the trace of one stored draw, from its call folder and the failures its checks gave."""
    receipt, output = files.load(folder / "receipt.json"), files.read(folder / "final.md")
    families, used = {fail.split(":")[0] for fail in fails}, receipt["usage"]
    cached, written = used.get("cached_input_tokens", 0), used.get("cache_write_input_tokens", 0)
    row = {"prompt_id": case["id"], "rep": rep, "prompt": case["brief"], "tags": case["tags"], "status": "ok",
           "stop_reason": "completed", "model": receipt["model"],
           "grade": {"pass": int(not fails), **{metric: int(family not in families) for family, metric in FAMILIES.items()}},
           "usage": {"input_tokens": used["input_tokens"] - cached - written, "cache_read_input_tokens": cached,
                     "cache_creation_input_tokens": written, "output_tokens": used["output_tokens"]},
           "latency_s": receipt["seconds"], "tokens": used["input_tokens"] + used["output_tokens"],
           "words": tells.words(output), "money_hits": len(checks.money(output, "pitch")),
           "admin_hits": len(checks.hits(checks.ADMIN, output)),
           "meta": {"agent": ":".join((receipt.get("agent", "codex"), receipt["model"], receipt["effort"])),
                    "cli": receipt["cli"], "fails": fails, "call": str(folder)}}
    if fails:
        row["explanation"] = {"pass": "; ".join(fails)}
    return row, [{"role": "system", "content": files.read(folder / "system.txt")},
                 {"role": "user", "content": files.read(folder / "prompt.txt")}, {"role": "assistant", "content": output}]


def draw(case: dict, rep: int, agent: str, call, briefs: Path) -> tuple[dict, list[dict]]:
    """One fresh pitch draw through serial.new, as (row, trace). A draw that fails its checks is a graded
    outcome; whatever leaves no checked answer raises, and never takes the (brief, rep) slot."""
    slug = f"{case['id']}-r{rep}"
    root = serial.folder(slug)
    with contextlib.suppress(serial.Stop):
        serial.new(slug, briefs / f"{case['id']}.txt", 1500, agent, call)
    drawn = serial.manifest(root)["stages"].get("ch00/pitch", {"draws": []})["draws"]
    if len(drawn) != 1 or files.read(root / "brief.md").strip() != case["brief"].strip():
        raise RuntimeError(f"{slug}: {len(drawn)} draws are recorded, not 1, or it holds another brief")
    row, trace = graded(case, rep, drawn[0]["fails"], root / "ch00" / "calls" / drawn[0]["dir"])
    row["meta"]["attempts"] = sum(1 for _ in (root / "ch00" / "calls").iterdir())
    return row, trace


def failure(error: Exception) -> str:
    """Why an attempt left no checked answer; none of these is a model failing a check."""
    text = str(error)
    if not isinstance(error, transport.Fault):
        return "harness_error"
    return ("timeout" if "timeout" in text else "refusal" if "stopped on refusal" in text
            else "serving_substitution" if "Served by" in text else "serving_error")


def run(args: argparse.Namespace, flow: Path, runner=None) -> int:
    sha, approved = harness()[0], (files.load(flow / "_state.json") if (flow / "_state.json").is_file() else {}).get("harness_sha")
    if approved != sha:
        print(f"needs you: the harness is {sha[:12]} and the approved one is {str(approved)[:12]}. Review the runner, "
              "the cases and the runtime, then run: python draws.py approve", file=sys.stderr)
        return 2
    agent, chosen = ":".join(transport.resolve(args.agent or serial.writer())), cases(args.only)
    variant, box, real, cap = flow / args.variant, files.box_lock(), os.environ.get("LITHARNESS_HOME"), serial.DRAWS
    files.lock(box, f"draws {args.variant}")
    try:
        serial.pinned(agent)
        name, model, _ = transport.resolve(agent)
        about = {"agent": agent, "harness": sha[:12], "model": model, "cli": transport.CLI[name][1], "commit": files.revision()[:12]}
        before = files.load(variant / "summary.json") if (variant / "summary.json").is_file() else about
        if (before["agent"], before["harness"]) != (agent, sha[:12]):
            raise ValueError(f"{args.variant} holds draws by {before['agent']} at harness {before['harness']}; name another --variant")
        files.save(variant / "summary.json", about | {"description": f"{agent} on {about['cli']}"})
        files.write(variant / "change.md", f"{agent} on {about['cli']}, harness {sha[:12]}\n")
        results, errors, briefs = variant / "results.jsonl", variant / "errors.jsonl", variant / "home" / "briefs"
        done = {(row["prompt_id"], row["rep"]) for row in load(results)}
        todo = [(case, rep) for rep in range(args.reps) for case in chosen if (case["id"], rep) not in done]
        os.environ["LITHARNESS_HOME"], serial.DRAWS = str(variant / "home"), 1  # one draw a row, in the variant's own home
        for case in chosen:
            files.write(briefs / f"{case['id']}.txt", case["brief"] + "\n")
        call = partial(transport.send, timeout=args.timeout_s, **({"runner": runner} if runner else {}))
        lock, stop, counts = threading.Lock(), threading.Event(), {"drawn": 0, "failed": 0, "streak": 0}

        def work(item: tuple[dict, int]) -> None:
            case, rep = item
            if stop.is_set():
                return
            try:
                row, trace = draw(case, rep, agent, call, briefs)
            except Exception as error:  # no checked answer: kept beside the rows, and a resume draws it again
                with lock:
                    counts["failed"], counts["streak"] = counts["failed"] + 1, counts["streak"] + 1
                    append(errors, {"prompt_id": case["id"], "rep": rep, "failure_class": failure(error), "model": model,
                                    "error": str(error)[:500], "usage": None, "utc": files.utc()})
                    wait = min(300, 15 * 2 ** counts["streak"]) * (0.5 + random.random())
                    if counts["streak"] >= STREAK:
                        stop.set()
                print(f"[{args.variant}] {case['id']} r{rep} FAILED ({failure(error)}): {error}", file=sys.stderr)
                time.sleep(wait if isinstance(error, transport.Fault) and not stop.is_set() else 0)  # jittered backoff
                return
            with lock:
                files.save(variant / "traces" / f"{case['id']}_rep{rep}.json", trace)
                append(results, row)
                counts["drawn"], counts["streak"] = counts["drawn"] + 1, 0
                said = "pass" if row["grade"]["pass"] else row["explanation"]["pass"][:100]
                print(f"[{args.variant}] {counts['drawn'] + counts['failed']}/{len(todo)} {case['id']} r{rep}: {said}", file=sys.stderr)

        print(f"[{args.variant}] {len(todo)} of {len(chosen) * args.reps} draws to run, by {agent}, {args.jobs} at a time", file=sys.stderr)
        with contextlib.redirect_stdout(io.StringIO()), ThreadPoolExecutor(args.jobs) as pool:
            list(pool.map(work, todo))
        print(f"[{args.variant}] {counts['drawn']} drawn, {counts['failed']} failed attempts"
              + f"; stopped after {STREAK} failures in a row, run again to resume" * stop.is_set(), file=sys.stderr)
        return 1 if counts["failed"] else 0
    finally:
        serial.DRAWS = cap
        if real is None:
            os.environ.pop("LITHARNESS_HOME", None)
        else:
            os.environ["LITHARNESS_HOME"] = real
        files.unlock(box)


def rates(found: list[dict], metric: str) -> dict[str, float]:
    """Per brief, the share of its draws that score 1: the brief is the independent unit, not the draw."""
    groups: dict[str, list[int]] = {}
    for row in found:
        groups.setdefault(row["prompt_id"], []).append(row["grade"][metric])
    return {case: statistics.fmean(values) for case, values in groups.items()}


def spread(values: list[float], form=lambda share: f"{100 * share:.0f}%") -> tuple[float, str, bool]:
    """The mean over briefs, its 95% interval from 2,000 seeded resamples of the briefs, and whether that
    interval holds zero. Fewer than BRIEFS briefs are not a sample of briefs, so they get no interval."""
    if len(values) < BRIEFS:
        return statistics.fmean(values), "too few briefs", True
    rng = random.Random(0)
    means = sorted(statistics.fmean(rng.choices(values, k=len(values))) for _ in range(2000))
    return statistics.fmean(values), f"{form(means[49])} to {form(means[1949])}", means[49] <= 0 <= means[1949]


def report(flow: Path) -> Path:
    names = sorted((p.name for p in flow.glob("*") if re.fullmatch(r"baseline|v[1-9]\d*", p.name) and load(p / "results.jsonl")),
                   key=lambda name: 0 if name == "baseline" else int(name[1:]))
    if not names:
        raise ValueError(f"no rows under {flow}")
    found, pct = {name: load(flow / name / "results.jsonl") for name in names}, lambda share: f"{100 * share:.0f}%"
    lines = [f"# Pitch draws ({files.utc()})", "", "One row is one fresh pitch draw. A brief's rate is the share of its draws that pass every hard "
             "check; a variant's rate is the mean of its briefs' rates, with a 95% interval from 2,000 resamples of the briefs. "
             "A description, never a verdict.", "", "| variant | agent | briefs | draws | passes | 95% interval | money clean | "
             "shape ok | leak clean | tokens a draw | seconds a draw | failed attempts |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for name in names:
        got, mine = found[name], rates(found[name], "pass")
        mean, band, _ = spread(list(mine.values()))
        others = " | ".join(pct(statistics.fmean(rates(got, metric).values())) for metric in FAMILIES.values())
        lines.append(f"| {name} | {files.load(flow / name / 'summary.json')['agent']} | {len(mine)} | {len(got)} | {pct(mean)} | "
                     f"{band} | {others} | {statistics.fmean(r['tokens'] for r in got):,.0f} | "
                     f"{statistics.fmean(r['latency_s'] for r in got):.0f} | {len(load(flow / name / 'errors.jsonl'))} |")
    base = rates(found[names[0]], "pass")
    lines += ["", f"## Against {names[0]}, brief by brief", "", "| variant | briefs in both | difference in passes | 95% interval | "
              "reads as |", "|---|---|---|---|---|"] * (len(names) > 1)
    for name in names[1:]:
        theirs = rates(found[name], "pass")
        deltas = [theirs[case] - base[case] for case in base if case in theirs]
        mean, band, noise = spread(deltas, lambda share: f"{100 * share:+.0f}")
        lines.append(f"| {name} | {len(deltas)} | {100 * mean:+.0f} points | {band} | "
                     f"{'too few briefs' if len(deltas) < BRIEFS else 'within noise' if noise else 'outside noise'} |")
    shown = len(lines)
    lines += ["", "## Briefs", "", f"| brief | tags | {' | '.join(names)} | commonest failures |", "|---|---|" + "---|" * (len(names) + 1)]
    for case in dict.fromkeys(row["prompt_id"] for name in names for row in found[name]):
        mine = {name: [row for row in found[name] if row["prompt_id"] == case] for name in names}
        why = Counter(kind for rows in mine.values() for row in rows  # each kind once a draw, however often it hit
                      for kind in dict.fromkeys(fail.split(" in: ")[0][:70] for fail in row["meta"]["fails"]))
        cells = " | ".join(f"{sum(row['grade']['pass'] for row in rows)}/{len(rows)}" if rows else "-" for rows in mine.values())
        tags = next(row["tags"] for rows in mine.values() for row in rows)
        lines.append(f"| {case} | {', '.join(tags)} | {cells} | {'; '.join(f'{what} x{n}' for what, n in why.most_common(3))} |")
    files.write(flow / "summary.md", "\n".join(lines) + "\n")
    print("\n".join(lines[:shown]))
    return flow / "summary.md"


def main(argv: list[str] | None = None, runner=None) -> int:
    parser = argparse.ArgumentParser(prog="draws.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    verbs = parser.add_subparsers(dest="verb", required=True)
    verbs.add_parser("approve")
    verbs.add_parser("report")
    go = verbs.add_parser("run")
    go.add_argument("--variant", default="baseline")
    go.add_argument("--agent")
    go.add_argument("--only")
    for flag, default in (("--reps", 4), ("--jobs", 2), ("--timeout-s", 300)):
        go.add_argument(flag, type=int, default=default)
    args, flow, code = parser.parse_args(argv), files.home() / "evals" / "pitch-draws", 0
    try:
        if args.verb == "approve":
            (sha, names), state = harness(), flow / "_state.json"
            files.save(state, (files.load(state) if state.is_file() else {}) | {
                "metrics": METRICS, "perf_fields": PERF, "harness_paths": names, "harness_sha": sha})
            print(f"approved: harness {sha[:12]} over {len(names)} files, recorded in {state}")
            return 0
        if args.verb == "run":
            if not re.fullmatch(r"baseline|v[1-9]\d*", args.variant) or min(args.reps, args.jobs, args.timeout_s) < 1:
                raise ValueError("--variant is baseline or vN; --reps, --jobs and --timeout-s are at least 1")
            code = run(args, flow, runner)
        if code != 2:
            print(f"\nwritten: {report(flow)}")
    except (serial.Stop, files.Held) as stop:
        print(f"needs you: {stop}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as fault:
        print(f"fault: {fault}", file=sys.stderr)
        return 2
    return code


if __name__ == "__main__":
    raise SystemExit(main())
