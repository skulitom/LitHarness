"""Stages over plain files under $LITHARNESS_HOME. Resuming means re-running the same command."""
from __future__ import annotations

from pathlib import Path
import re

from . import checks, files, prompts, sheet, tells, transport

DRAWS, RETRIES, MAX_REQUEST, MAX_CHAPTERS, BRIEF_WORDS, OVER_TOKENS = 3, 2, 32_000, 10, 150, 30_000


class Stop(Exception):
    """Needs a person (exit 1): drawn out, located in our request, or refused before spending."""


def folder(slug: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", slug):
        raise ValueError("A slug is lowercase letters, digits and hyphens")
    return files.home() / "serials" / slug


def text(root: Path, name: str) -> str:
    return files.read(root / name) if (root / name).is_file() else ""


def manifest(root: Path) -> dict:
    found = files.load(root / "manifest.json") if (root / "manifest.json").is_file() else {}
    return {"stages": {}, "files": {}, **found}


def keep(root: Path, name: str, body: str) -> None:
    """Write a stage's file and record its hash, so status can flag a later hand edit."""
    record = manifest(root)
    record["files"][name] = files.write(root / name, body)
    files.save(root / "manifest.json", record)


def done(root: Path) -> int:
    return next(n for n in range(100) if not (root / f"ch{n + 1:02d}" / "report.md").is_file())


def writer(switch: str | None = None) -> str:
    """The one agent that writes for the whole project, as agent:model:effort, kept in $LITHARNESS_HOME/agent.
    A switch ('claude', 'codex:gpt-6-astra:high') holds from the next command on, for every serial."""
    record = files.home() / "agent"
    if switch:
        files.write(record, ":".join(transport.resolve(switch)) + "\n")
    return ":".join(transport.resolve(files.read(record).strip() if record.is_file() else "codex"))


def pinned(agent: str) -> None:
    """Refuses, before anything is spent, an agent that is not signed in or whose installed CLI version
    has not passed the canary."""
    name, record = transport.resolve(agent)[0], files.home() / "canary.json"
    version = transport.preflight(name)
    if (files.load(record) if record.is_file() else {}).get(name, {}).get("version") != version:
        raise Stop(f"{version} has not passed the canary; run: python -m litharness canary {name}")


def totals(rows: list[dict]) -> dict:
    usage = {name: sum(r["usage"].get(name, 0) for r in rows if r.get("usage") is not None)
             for name in ("input_tokens", "cached_input_tokens", "output_tokens")}
    return {"calls": len(rows), "seconds": round(sum(r.get("seconds", 0) for r in rows), 3),
            "unknown_usage_calls": sum(r.get("usage") is None for r in rows), **usage,
            "uncached_input_tokens": usage["input_tokens"] - usage["cached_input_tokens"]}


def usage(root: Path, n: int) -> str:
    total = totals([files.load(p) for p in sorted((root / f"ch{n:02d}").glob("calls/*/receipt.json"))])
    tokens = total["input_tokens"] + total["output_tokens"]
    draws = ", ".join(f"{name[5:]} {entry['draws'][-1]['k']} of {entry['draws'][-1]['of']}"
                      for name, entry in manifest(root)["stages"].items()
                      if name.startswith(f"ch{n:02d}/") and entry["draws"])
    return (f"draws {draws}; {total['calls']} calls; {tokens} tokens (cached {total['cached_input_tokens']},"
            f" uncached {total['uncached_input_tokens']}, {total['unknown_usage_calls']} calls unknown);"
            f" {total['seconds']:.0f} s" + (f"; OVER {OVER_TOKENS}" if tokens > OVER_TOKENS else ""))


def ask(calls: Path, name: str, prompt: str, call, agent: str) -> tuple[str, str]:
    """(answer, call folder). A completed receipt for this exact prompt and agent is adopted without
    spending; a transport fault is retried at most RETRIES times and never counts as a draw."""
    attempts, suffix, fault = 0, 0, None
    while attempts <= RETRIES:
        directory, suffix = calls / (name if suffix == 0 else f"{name}r{suffix}"), suffix + 1
        if directory.exists():
            receipt = files.load(directory / "receipt.json") if (directory / "receipt.json").is_file() else {}
            final, asked = directory / "final.md", (receipt.get("agent", "codex"), receipt.get("model"), receipt.get("effort"))
            if (receipt.get("status") == "completed" and final.is_file() and receipt.get("output_sha256")
                    == files.digest(final) and receipt.get("prompt_sha256") == files.sha(prompt.encode())
                    and asked == transport.resolve(agent)):
                return files.read(final), directory.name
            continue
        attempts += 1
        try:
            answer, _ = call(prompt, directory, system=prompts.SYSTEM, agent=agent)
            return answer, directory.name
        except transport.Fault as error:
            fault = error
    raise transport.Fault(f"{name}: the call and {RETRIES} retries failed: {fault}")


def locate(word: str, stage: str, parts: list[tuple[str, str, str]]) -> str | None:
    """Where our own request carries the money word the model returned (any listed form of it,
    so 'rents' in the brief locates 'rent' and 'owes' locates 'owed'), as file:line, or None."""
    def root(form: str) -> str:
        return "owe" if form in {"owe", "owes", "owed", "owing"} else form[:4]
    for _, source, body in parts:
        for number, line in enumerate(body.splitlines(), 1):
            if any(root(sent) == root(word) for sent, _ in checks.money(line, stage)):
                return f"{source}:{number}"
    return None


def checked(check, output: str) -> list[str]:
    try:
        return check(output)
    except Exception as error:  # a check that breaks on an answer is recorded as a failed draw
        return [f"check: {type(error).__name__}: {error}"]


def stage(root: Path, n: int, name: str, template: str, parts: list[tuple[str, str, str]], check,
          call, agent: str) -> str:
    """Draw until the output passes its hard checks: at most DRAWS per input set, numbered on. The agent
    belongs to the input set, so switching it opens a new window like any other changed input; a draw
    stored before agents were recorded was Codex's."""
    rendered = template.format(n=n, words=files.load(root / "serial.json")["words"])
    prompt = rendered + "".join(f"\n{prompts.PARTS[label]}:\n{body.strip()}\n" for label, _, body in parts)
    if len(prompt) > MAX_REQUEST:
        raise ValueError(f"ch{n:02d} {name}: the request is {len(prompt)} characters, over {MAX_REQUEST}")
    sent = {f"prompts.{name}": files.sha(rendered.encode()), "prompts.SYSTEM": files.sha(prompts.SYSTEM.encode()),
            **{source: files.sha(body.encode()) for _, source, body in parts}}
    key, record = files.sha(repr(sorted(sent.items())).encode()), manifest(root)
    entry = record["stages"].setdefault(f"ch{n:02d}/{name}", {"draws": []})
    same = [d for d in entry["draws"] if (d["inputs"], d.get("agent", "codex:gpt-6-astra:medium")) == (key, agent)]
    calls, window = root / f"ch{n:02d}" / "calls", len(entry["draws"]) - len(same) + DRAWS
    stored = [d for d in same if (calls / d["dir"] / "final.md").is_file()]
    for draw in [d for d in stored[::-1] if not d["fails"]] + [d for d in stored if d["fails"]]:
        # A stored answer that passes the checks as they are now is adopted; a fixed check never buys it again.
        if not draw["fails"] or not checked(check, files.read(calls / draw["dir"] / "final.md")):
            if draw["fails"]:
                draw.update(fails=[], located=None, rechecked=files.utc())
                files.save(root / "manifest.json", record)
            return files.read(calls / draw["dir"] / "final.md")
    while len(same) < DRAWS and not (same and same[-1]["located"]):
        k = len(entry["draws"]) + 1
        print(f"ch{n:02d} {name}: draw {k} of {window}", flush=True)
        output, directory = ask(calls, f"{name}-d{k}", prompt, call, agent)
        fails = checked(check, output)
        words = [fail.split("'")[1] for fail in fails if fail.startswith("money: ")]
        places = [f"'{w}' in {place}" for w in words if (place := locate(
            w, "pitch" if name == "pitch" else "chapter", [("", f"prompts.{name.upper()}", rendered), *parts]))]
        same.append({"k": k, "of": window, "dir": directory, "agent": agent, "inputs": key, "sent": sent, "fails": fails,
                     "output": files.sha(output.encode()), "located": places[0] if places else None})
        entry["draws"].append(same[-1])
        files.save(root / "manifest.json", record)
        if not fails:
            return output
    last = same[-1]
    where = f"located in our request: {last['located']}" if last["located"] else f"{len(same)} draws failed"
    raise Stop(f"ch{n:02d} {name}: {where}\n  " + "\n  ".join(last["fails"]))


def new(slug: str, brief_file: Path, words: int, agent: str, call=transport.send) -> Path:
    """Create the serial and draw its pitch (bible and start sheet) for the operator's glance."""
    root, brief = folder(slug), files.read(brief_file)
    if not brief.strip() or tells.words(brief) > BRIEF_WORDS or not 500 <= words <= 1700:
        # A draft request carries the bible, state, plan and a previous chapter of up to 1.8x the target:
        # above 1,700 words it can pass MAX_REQUEST after chapter 1 is already paid for.
        raise ValueError(f"A brief is 1-{BRIEF_WORDS} words and a chapter 500-1700 words")
    if not (root / "serial.json").is_file():
        root.mkdir(parents=True, exist_ok=True)
        keep(root, "brief.md", brief)
        files.save(root / "serial.json", {"words": words, "repo": files.revision(), "brief": files.sha(brief.encode())})
    elif files.load(root / "serial.json")["brief"] != files.sha(brief.encode()):
        raise Stop(f"{slug} exists with a different brief; edit its brief.md, or choose another slug")
    if not (root / "ch00" / "bible.md").is_file():
        bible = stage(root, 0, "pitch", prompts.PITCH, [("brief", "brief.md", text(root, "brief.md"))],
                      lambda out: checks.hard("pitch", out), call, agent)
        keep(root, "ch00/sheet.txt", sheet.render(sheet.start(checks.section(bible, "System") or "")))
        keep(root, "ch00/bible.md", bible)
    return root / "ch00" / "bible.md"


def chapter(root: Path, n: int, call, agent: str) -> Path:
    """Plan, draft, normalize, check, located rewrite, sheet and report for chapter n."""
    here, last, target = f"ch{n:02d}", f"ch{n - 1:02d}", files.load(root / "serial.json")["words"]
    bible, before_text = text(root, "ch00/bible.md"), text(root, f"{last}/sheet.txt")
    ranks, before = sheet.ladder(checks.section(bible, "System") or ""), sheet.read(before_text)
    base = [("brief", "brief.md", text(root, "brief.md")), ("bible", "ch00/bible.md", bible),
            ("sheet", f"{last}/sheet.txt", before_text)]
    previous = [("previous", f"{last}/chapter.md", text(root, f"{last}/chapter.md"))] * (n > 1)
    if not (root / here / "plan.md").is_file():
        state = [("state", f"{last}/state.md", text(root, f"{last}/state.md"))] * (n > 1)
        output = stage(root, n, "plan", prompts.PLAN, base + state + previous,
                       lambda out: checks.hard("plan", out, n=n, ranks=ranks, before=before), call, agent)
        keep(root, f"{here}/state.md", checks.split(output)[0])
        keep(root, f"{here}/plan.md", checks.split(output)[1])
    plan = text(root, f"{here}/plan.md")
    rise_plan = checks.planned(plan)
    if not (root / here / "chapter.md").is_file():
        parts = base + [("state", f"{here}/state.md", text(root, f"{here}/state.md")),
                        ("plan", f"{here}/plan.md", plan)] + previous
        raw = stage(root, n, "draft", prompts.DRAFT, parts, lambda out: checks.hard(
            "chapter", checks.normalize(out)[0], raw=out, target=target, n=n, before=before, ranks=ranks,
            rise_plan=rise_plan), call, agent)
        files.write(root / here / "final.md", raw)
        keep(root, f"{here}/chapter.md", checks.normalize(raw)[0])
    fixes = rewrite(root, n, call, agent)
    body, raw = text(root, f"{here}/chapter.md"), text(root, f"{here}/final.md")
    keep(root, f"{here}/sheet.txt", sheet.render(sheet.replay(before, body, ranks)[0]))
    files.write(root / here / "report.md", f"# {checks.title(plan, 'plan')}\n\n" + checks.report(
        body, raw=raw, target=target, n=n, plan=plan, bible=bible, before=before, ranks=ranks,
        fixes=fixes, usage=usage(root, n), normalized=checks.normalize(raw)[1]))
    return root / here / "report.md"


def rewrite(root: Path, n: int, call, agent: str) -> list[tuple[str, str]]:
    """When 2 or more tell families run over their ceilings, one call says the located sentences
    again (only sentences that occur once, so a rewrite lands where it was located). A rewrite is kept,
    normalized, only if it clears the counter and the money, leak and person checks. The pairs are
    recorded first and applied to the normalized draft, so a resumed run re-applies, never re-asks."""
    record, name = manifest(root), f"ch{n:02d}/rewrite"
    base = checks.normalize(text(root, f"ch{n:02d}/final.md"))[0]
    if name not in record["stages"]:
        located, over, told, fixes = tells.locate(base), tells.over(base), tells.sentences(base), []
        wanted = [s for s in dict.fromkeys(s for f in over for s in located[f]) if base.count(s) == 1] * (len(over) > 1)
        lines = [prompts.REWRITE_LINE.format(i=i, ask=" ".join(prompts.ASKS[f] for f in tells.CEILINGS if s in located[f]),
                                             before=told[told.index(s) - 1] if told.index(s) > 0 else "-", sentence=s)
                 for i, s in enumerate(wanted, 1)]
        request = prompts.REWRITE + "\n".join(lines) + "\n"
        asked = wanted and len(request) <= MAX_REQUEST
        answer = ask(root / f"ch{n:02d}" / "calls", "rewrite-d1", request, call, agent)[0] if asked else ""
        for number, new in re.findall(r"^[ \t]*(\d+)\.[ \t]+(.+?)[ \t]*$", answer, re.M):
            old, new = wanted[int(number) - 1] if 0 < int(number) <= len(wanted) else "", checks.normalize(new)[0].strip()
            if (old and not any(tells.locate(new)[f] for f in tells.CEILINGS)
                    and not (checks.money(new, "chapter") or checks.leak(new) or checks.person(new))):
                fixes.append((old, new))
        record["stages"][name] = {"draws": [], "fixes": fixes, "skipped": bool(wanted) and not asked}
        files.save(root / "manifest.json", record)
    fixes = [tuple(fix) for fix in record["stages"][name]["fixes"]]
    for old, new in fixes:
        base = base.replace(old, new, 1)
    keep(root, f"ch{n:02d}/chapter.md", base)
    return fixes


def next_chapters(slug: str, count: int, agent: str, call=transport.send):
    """Yields each chapter's report as it is finished, so a later stop never hides earlier chapters."""
    root = folder(slug)
    if not (root / "ch00" / "bible.md").is_file():
        raise Stop(f"{slug} has no pitch yet; run: new {slug} --brief FILE")
    if not 1 <= count <= MAX_CHAPTERS:
        raise ValueError(f"-n is 1 to {MAX_CHAPTERS}")
    for _ in range(count):
        yield chapter(root, done(root) + 1, call, agent)


def redraw(slug: str, start: int) -> Path:
    """Move chapter `start` and every later one (0: the pitch too) to attempts/<utc>/. Nothing is deleted."""
    root = folder(slug)
    moving = [p for p in sorted(root.glob("ch[0-9][0-9]")) if int(p.name[2:]) >= start]
    if not moving:
        raise Stop(f"{slug} has nothing at or after ch{start:02d}")
    record, stamp = manifest(root), files.utc()
    aside = next(p for i in range(1000) if not (p := root / "attempts" / (stamp + f"-{i}" * bool(i))).exists())
    aside.mkdir(parents=True)
    files.save(aside / "manifest.json", record)
    for path in reversed(moving):  # last first, so a failure part way leaves an unbroken prefix of chapters
        path.rename(aside / path.name)
        record["stages"] = {k: v for k, v in record["stages"].items() if not k.startswith(path.name + "/")}
        files.save(root / "manifest.json", record)
    return aside


def status(slug: str | None = None) -> str:
    roots = [folder(slug)] if slug else sorted(p for p in (files.home() / "serials").glob("*") if p.is_dir())
    out = []
    for root in roots:
        n, record = done(root), manifest(root)
        words = sum(tells.words(text(root, f"ch{i:02d}/chapter.md")) for i in range(1, n + 1))
        rows = totals([files.load(p) for p in root.glob("ch[0-9][0-9]/calls/*/receipt.json")])
        out.append(f"{root.name}: {n} chapters, {words} words, {rows['calls']} calls, "
                   f"{rows['input_tokens'] + rows['output_tokens']} tokens")
        for name, entry in record["stages"].items():
            if entry["draws"] and all(draw["fails"] for draw in entry["draws"]):
                out += [f"  {name}: draw {len(entry['draws'])} failed" + (f", located in our request: "
                        f"{entry['draws'][-1]['located']}" if entry["draws"][-1]["located"] else "")]
                out += [f"    {fail}" for fail in entry["draws"][-1]["fails"]]
        out += [f"  hand-edited: {name}" for name, sha in record["files"].items()
                if (root / name).is_file() and files.digest(root / name) != sha]
        out += [f"  lock held: {text(root, 'lock/holder').strip()}"] * (root / "lock").exists()
        step = f"next {root.name}" if (root / "ch00" / "bible.md").is_file() else f"new {root.name} --brief FILE"
        out.append(f"  next: python -m litharness {step}")
    return "\n".join(out) or f"no serials under {files.home() / 'serials'}"
