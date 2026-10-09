"""How often chapter 1's plan and draft pass their hard checks on their first draw, from fixed passing bibles.

    python experiments/2026-10-09-chapter-draws/chapter_draws.py prepare    fix 4 passing v32 bibles a brief; no call
    python experiments/2026-10-09-chapter-draws/chapter_draws.py approve    record the hash of runner, bibles and runtime
    python experiments/2026-10-09-chapter-draws/chapter_draws.py run --variant c0 --agent api:claude-haiku-5-5:high
                                                       [--DANGER-API-USE] [--reps 4] [--jobs 16] [--timeout-s 600]
    python experiments/2026-10-09-chapter-draws/chapter_draws.py compare BASE NEW [METRIC]

One row is one chapter-1 attempt from a fixed bible in a fresh serial: serial.chapter with one draw a stage, so a
failure that would cost a redraw is a failed row, graded by the app's own checks as the manifest recorded them. A
description, never a verdict: the operator's read of a chapter stays the gate. Data lives under
$LITHARNESS_HOME/evals/chapter-draws/, outside the repo, and nothing imports from experiments/.
"""
from __future__ import annotations

import argparse
import collections
from concurrent.futures import ThreadPoolExecutor
import contextlib
from functools import partial
import json
import os
from pathlib import Path
import random
import statistics
import sys
import threading

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from litharness import checks, files, serial, sheet, tells, transport  # noqa: E402

SOURCE, PER_BRIEF, STREAK = "v32", 4, 6  # the pitch variant whose passing bibles are fixed; consecutive faults stop a run
PRICES = {"claude-haiku-5-5": (0.10, 0.50)}  # $ per million input / output tokens, prompts up to 100K


def flow() -> Path:
    return files.home() / "evals" / "chapter-draws"


def load(path: Path) -> list[dict]:
    found = []
    for line in files.read(path).splitlines() if path.is_file() else []:
        with contextlib.suppress(ValueError):
            found.append(json.loads(line))
    return found


def append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "ab") as handle:
        handle.write(json.dumps(row, ensure_ascii=False).encode("utf-8") + b"\n")
        handle.flush()
        os.fsync(handle.fileno())


def harness() -> str:
    """One hash over this runner, the fixed bibles and the runtime: what is approved before anything is spent."""
    base = flow()
    paths = [Path(__file__).resolve(), base / "bibles.json", *sorted((base / "bibles").glob("*.md")),
             *sorted((ROOT / "litharness").glob("*.py"))]
    return files.sha(b"".join(p.name.encode() + b"\0" + p.read_bytes() + b"\0" for p in paths))


def prepare() -> None:
    """Fix the first PER_BRIEF passing bibles of each brief in SOURCE, once; a later prepare refuses."""
    base = flow()
    if (base / "bibles.json").is_file():
        raise ValueError(f"{base / 'bibles.json'} exists: the bibles are fixed once")
    rows = load(files.home() / "evals" / "pitch-draws" / SOURCE / "results.jsonl")
    chosen, fixed = collections.defaultdict(list), {}
    for row in sorted(rows, key=lambda r: (r["prompt_id"], r["rep"])):
        if row["grade"]["pass"] and len(chosen[row["prompt_id"]]) < PER_BRIEF:
            chosen[row["prompt_id"]].append(row)
    for case, picked in sorted(chosen.items()):
        for i, row in enumerate(picked):
            bible = files.read(Path(row["meta"]["call"]) / "final.md")
            key = f"{case}-b{i}"
            files.write(base / "bibles" / f"{key}.md", bible)
            fixed[key] = {"case": case, "brief": row["prompt"], "source": row["meta"]["call"], "sha256": files.sha(bible.encode())}
    files.save(base / "bibles.json", fixed)
    print(f"fixed {len(fixed)} bibles from {SOURCE}, {PER_BRIEF} a brief")


def attempt(key: str, item: dict, bible: str, rep: int, agent: str, call) -> dict:
    """One chapter-1 attempt in a fresh serial built as serial.new leaves one; a stored draw is adopted on resume."""
    root, brief = serial.folder(f"{key}-r{rep}"), item["brief"].strip() + "\n"
    if not (root / "serial.json").is_file():
        root.mkdir(parents=True, exist_ok=True)
        serial.keep(root, "brief.md", brief)
        serial.keep(root, "ch00/sheet.txt", sheet.render(sheet.start(checks.section(bible, "System") or "")))
        serial.keep(root, "ch00/bible.md", bible)
        files.save(root / "serial.json", {"words": 1500, "repo": files.revision(), "brief": files.sha(brief.encode())})
    stopped = ""
    try:
        serial.chapter(root, 1, call, agent)
    except serial.Stop as stop:
        stopped = str(stop).splitlines()[0]
    stages = serial.manifest(root)["stages"]
    plan, draft = (stages.get(f"ch01/{name}", {"draws": []})["draws"] for name in ("plan", "draft"))
    plan_fails = plan[0]["fails"] if plan else ["plan: no draw recorded"]
    draft_fails = draft[0]["fails"] if draft else None
    receipts = [files.load(p) for p in sorted((root / "ch01" / "calls").glob("*/receipt.json"))]
    used, chapter = serial.totals(receipts), serial.text(root, "ch01/chapter.md")
    return {"prompt_id": item["case"], "bible": key, "rep": rep,
            "grade": {"chapter_pass": int(not plan_fails and draft_fails == []), "plan_pass": int(not plan_fails),
                      "draft_pass": None if draft_fails is None else int(not draft_fails)},
            "fails": {"plan": plan_fails, "draft": draft_fails or []},
            "families": sorted({f.split(":")[0] for f in plan_fails + (draft_fails or [])}),
            "rewrites": len(stages.get("ch01/rewrite", {}).get("fixes", [])), "words": tells.words(chapter) if chapter else 0,
            "usage": {k: used[k] for k in ("input_tokens", "output_tokens", "cached_input_tokens")}, "calls": used["calls"],
            "latency_s": used["seconds"], "model": receipts[0]["model"] if receipts else None, "stopped": stopped,
            "folder": str(root)}


def run(args: argparse.Namespace) -> int:
    base, sha = flow(), harness()
    approved = (files.load(base / "_state.json") if (base / "_state.json").is_file() else {}).get("harness_sha")
    if approved != sha:
        print(f"needs you: the harness is {sha[:12]} and the approved one is {str(approved)[:12]}; run approve", file=sys.stderr)
        return 2
    transport.DANGER = args.danger
    agent, fixed = ":".join(transport.resolve(args.agent)), files.load(base / "bibles.json")
    texts = {key: files.read(base / "bibles" / f"{key}.md") for key in fixed}
    variant, box, real = base / args.variant, files.box_lock(), os.environ.get("LITHARNESS_HOME")
    files.lock(box, f"chapter-draws {args.variant}")
    try:
        serial.pinned(agent)  # fixes the api key's path before the home moves
        about = {"agent": agent, "harness": sha[:12], "commit": files.revision()[:12]}
        before = files.load(variant / "summary.json") if (variant / "summary.json").is_file() else about
        if (before["agent"], before["harness"]) != (agent, sha[:12]):
            raise ValueError(f"{args.variant} holds rows by {before['agent']} at harness {before['harness']}; name another variant")
        files.save(variant / "summary.json", about)
        results = variant / "results.jsonl"
        done = {(row["bible"], row["rep"]) for row in load(results)}
        todo = [(key, rep) for rep in range(args.reps) for key in sorted(fixed) if (key, rep) not in done]
        os.environ["LITHARNESS_HOME"], serial.DRAWS = str(variant / "home"), 1
        call, lock, stop = partial(transport.send, timeout=args.timeout_s), threading.Lock(), threading.Event()
        counts = {"drawn": 0, "failed": 0, "streak": 0}

        def work(item: tuple[str, int]) -> None:
            key, rep = item
            if stop.is_set():
                return
            try:
                row = attempt(key, fixed[key], texts[key], rep, agent, call)
            except Exception as error:  # a fault left no checked chapter: logged, never a row
                with lock:
                    counts["failed"], counts["streak"] = counts["failed"] + 1, counts["streak"] + 1
                    append(variant / "errors.jsonl", {"bible": key, "rep": rep, "error": f"{type(error).__name__}: {error}"[:600]})
                    if counts["streak"] >= STREAK:
                        stop.set()
                return
            with lock:
                append(results, row)
                counts["drawn"], counts["streak"] = counts["drawn"] + 1, 0
                if counts["drawn"] % 25 == 0:
                    print(f"[{args.variant}] {counts['drawn']}/{len(todo)}", file=sys.stderr, flush=True)

        print(f"[{args.variant}] {len(todo)} attempts to run by {agent}, {args.jobs} at a time", file=sys.stderr, flush=True)
        with ThreadPoolExecutor(args.jobs) as pool:
            list(pool.map(work, todo))
        print(f"[{args.variant}] {counts['drawn']} drawn, {counts['failed']} failed attempts"
              + (f"; stopped after {STREAK} faults in a row" if stop.is_set() else ""), file=sys.stderr)
        return 1 if stop.is_set() else 0
    finally:
        if real is None:
            os.environ.pop("LITHARNESS_HOME", None)
        else:
            os.environ["LITHARNESS_HOME"] = real
        files.unlock(box)


def describe(name: str) -> list[dict]:
    rows = load(flow() / name / "results.jsonl")
    n, fam = len(rows), collections.Counter(f for r in rows for f in r["families"])
    rate = lambda m: [r["grade"][m] for r in rows if r["grade"][m] is not None]  # noqa: E731
    cost = sum(PRICES.get(r["model"] or "", (0, 0))[0] * r["usage"]["input_tokens"] / 1e6
               + PRICES.get(r["model"] or "", (0, 0))[1] * r["usage"]["output_tokens"] / 1e6 for r in rows)
    shown = ", ".join(f"{m} {sum(rate(m))}/{len(rate(m))}" for m in ("chapter_pass", "plan_pass", "draft_pass"))
    print(f"{name}: {n} rows; {shown}; failing families {dict(fam.most_common(6))}; rewrites in "
          f"{sum(r['rewrites'] > 0 for r in rows)}; median words {statistics.median([r['words'] for r in rows if r['words']] or [0])}; "
          f"{statistics.mean([r['calls'] for r in rows] or [0]):.1f} calls; ${cost:.2f}")
    return rows


def compare(base: str, new: str, metric: str) -> None:
    """Brief by brief, as draws.py: a variant's rate is the mean of its briefs' rates; 95% from 2,000 resamples."""
    def rates(rows):
        by = collections.defaultdict(list)
        for row in rows:
            if row["grade"][metric] is not None:
                by[row["prompt_id"]].append(row["grade"][metric])
        return {k: sum(v) / len(v) for k, v in by.items()}
    a, b = rates(describe(base)), rates(describe(new))
    briefs = sorted(set(a) & set(b))
    diffs, rng = [b[k] - a[k] for k in briefs], random.Random(7)
    boots = sorted(sum(rng.choice(diffs) for _ in diffs) / len(diffs) for _ in range(2000))
    low, high, mean = boots[49], boots[1949], sum(diffs) / len(diffs)
    print(f"{metric}: {base} {sum(a[k] for k in briefs) / len(briefs):.0%} -> {new} {sum(b[k] for k in briefs) / len(briefs):.0%};"
          f" {mean * 100:+.0f} points [{low * 100:+.0f}, {high * 100:+.0f}] over {len(briefs)} briefs;"
          f" {'outside' if low > 0 or high < 0 else 'within'} noise")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="chapter_draws.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    verbs = parser.add_subparsers(dest="verb", required=True)
    verbs.add_parser("prepare")
    verbs.add_parser("approve")
    go = verbs.add_parser("run")
    go.add_argument("--variant", required=True)
    go.add_argument("--agent", required=True)
    go.add_argument("--DANGER-API-USE", dest="danger", action="store_true")
    for flag, default in (("--reps", 4), ("--jobs", 16), ("--timeout-s", 600)):
        go.add_argument(flag, type=int, default=default)
    versus = verbs.add_parser("compare")
    versus.add_argument("base")
    versus.add_argument("new")
    versus.add_argument("metric", nargs="?", default="chapter_pass")
    args = parser.parse_args(argv)
    try:
        if args.verb == "prepare":
            prepare()
        elif args.verb == "approve":
            state = flow() / "_state.json"
            files.save(state, (files.load(state) if state.is_file() else {}) | {"harness_sha": harness()})
            print(f"approved: harness {harness()[:12]}")
        elif args.verb == "run":
            return run(args)
        else:
            compare(args.base, args.new, args.metric)
    except (serial.Stop, files.Held) as stop:
        print(f"needs you: {stop}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as fault:
        print(f"fault: {fault}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
