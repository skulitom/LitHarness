"""python -m litharness VERB. Exit codes: 0 done, 1 needs a person, 2 fault."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

from . import checks, files, serial, sheet, transport


def check(path: Path, stage: str, slug: str | None) -> tuple[list[str], str]:
    """Every deterministic check on any text; without a serial it is chapter 1 with no plan or bible."""
    raw, root = files.read(path).replace("\r\n", "\n"), serial.folder(slug) if slug else None
    inside = [p.name for p in path.resolve().parents if root and p.parent == root.resolve()]
    n = int(inside[0][2:]) if inside and re.fullmatch(r"ch\d\d", inside[0]) else 0 if stage == "plan" and not root else 1
    bible = serial.text(root, "ch00/bible.md") if root else ""
    ranks, before = sheet.ladder(checks.section(bible, "System") or ""), sheet.read(
        serial.text(root, f"ch{n - 1:02d}/sheet.txt") if root and n else "")
    if stage == "plan" and "=== PLAN ===" not in raw:  # a stored plan.md: its state is the file beside it
        state = files.read(path.parent / "state.md") if (path.parent / "state.md").is_file() else ""
        raw = f"=== STATE ===\n{state}\n=== PLAN ===\n{raw}"
    if stage != "chapter":
        return checks.hard(stage, raw, n=n, ranks=ranks, before=before), ""
    body, counts = checks.normalize(raw)
    plan = serial.text(root, f"ch{n:02d}/plan.md") if root else ""
    context = {"target": files.load(root / "serial.json")["words"] if root else 1500, "n": n, "ranks": ranks,
               "before": before}
    fails = checks.hard("chapter", body, raw=raw, rise_plan=checks.planned(plan), **context)
    return fails, checks.report(body, raw=raw, plan=plan, bible=bible, normalized=counts, **context)


def spend(args: argparse.Namespace) -> int:
    """new and next by the project's agent, canary by it or by the one named: box lock, canary pin, serial lock."""
    if args.verb == "next" and not serial.folder(args.slug).is_dir():
        raise serial.Stop(f"there is no serial {args.slug}; run: new {args.slug} --brief FILE")
    agent, box = ":".join(transport.resolve(getattr(args, "agent", None) or serial.writer())), files.box_lock()
    files.lock(box, f"{args.verb} {getattr(args, 'slug', '-')}")
    try:
        if args.verb == "canary":
            leaked = transport.canary(agent)
            pinned = f"canary: NONE; {agent} on {transport.CLI[transport.resolve(agent)[0]][1]} pinned"
            print(f"canary: {agent} leaked {', '.join(leaked)}" if leaked else pinned)
            return 1 if leaked else 0
        serial.pinned(agent)
        root = serial.folder(args.slug)
        files.lock(root / "lock", f"{args.verb} {args.slug}")
        try:
            if args.verb == "new":
                print(f"pitch ready for your glance: {serial.new(args.slug, args.brief, args.words, agent)}")
            for report in serial.next_chapters(args.slug, args.n, agent) if args.verb == "next" else []:
                print(f"chapter ready: {report.parent / 'chapter.md'} (report: {report.name})")
        finally:
            files.unlock(root / "lock")
    finally:
        files.unlock(box)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="litharness", description=__doc__)
    verbs = parser.add_subparsers(dest="verb", required=True)
    new = verbs.add_parser("new", help="create a serial and draw its pitch for your glance")
    new.add_argument("slug")
    new.add_argument("--brief", type=Path, required=True)
    new.add_argument("--words", type=int, default=1500)
    after = verbs.add_parser("next", help="plan, draft, check and report the next chapters")
    after.add_argument("slug")
    after.add_argument("-n", type=int, default=1)
    agent = verbs.add_parser("agent", help="show, or switch, the one agent that writes for the whole project")
    agent.add_argument("switch", nargs="?", metavar="codex|claude[:MODEL[:EFFORT]]")
    verbs.add_parser("status", help="read-only: chapters, draws, failing checks, tokens").add_argument("slug", nargs="?")
    redraw = verbs.add_parser("redraw", help="move chapter N and later aside (0: the pitch too)")
    redraw.add_argument("slug")
    redraw.add_argument("--from", dest="start", type=int, required=True)
    test = verbs.add_parser("check", help="every deterministic check on any text; no calls")
    test.add_argument("file", type=Path)
    test.add_argument("--stage", choices=("pitch", "plan", "chapter"), default="chapter")
    test.add_argument("--serial")
    verbs.add_parser("canary", help="live isolation canary; pins an agent's CLI version").add_argument("agent", nargs="?")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    try:
        if args.verb == "agent":
            print(serial.writer(args.switch))
        elif args.verb == "status":
            holder = files.box_lock() / "holder"
            print(serial.status(args.slug) + f"\nagent: {serial.writer()}"
                  f"\nbox: {files.read(holder).strip() if holder.is_file() else 'free'}")
        elif args.verb == "check":
            fails, report = check(args.file, args.stage, args.serial)
            print("\n".join(fails or ["hard checks: all pass"]) + ("\n\n" + report if report else ""))
            return 1 if fails else 0
        elif args.verb == "redraw":
            if not serial.folder(args.slug).is_dir():
                raise serial.Stop(f"there is no serial {args.slug}")
            lock = serial.folder(args.slug) / "lock"
            files.lock(lock, f"redraw {args.slug}")
            try:
                print(f"moved aside to {serial.redraw(args.slug, args.start)}")
            finally:
                files.unlock(lock)
        else:
            return spend(args)
    except (serial.Stop, files.Held) as stop:
        print(f"needs you: {stop}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as fault:
        print(f"fault: {fault}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
