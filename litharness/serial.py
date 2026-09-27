"""Stages over plain files under $LITHARNESS_HOME. Resuming means re-running the same command."""
from __future__ import annotations

from pathlib import Path
import re

from . import checks, files, prompts, sheet, tells, transport

MODEL, EFFORT = "gpt-6-astra", "medium"
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
    n = 0
    while (root / f"ch{n + 1:02d}" / "report.md").is_file():
        n += 1
    return n


def totals(rows: list[dict]) -> dict:
    usage = {name: sum(r["usage"].get(name, 0) for r in rows if r.get("usage") is not None)
             for name in ("input_tokens", "cached_input_tokens", "output_tokens")}
    return {"calls": len(rows), "seconds": round(sum(r.get("seconds", 0) for r in rows), 3),
            "unknown_usage_calls": sum(r.get("usage") is None for r in rows), **usage,
            "uncached_input_tokens": usage["input_tokens"] - usage["cached_input_tokens"]}


def usage(root: Path, n: int) -> str:
    total = totals([files.load(p) for p in sorted((root / f"ch{n:02d}").glob("calls/*/receipt.json"))])
    tokens = total["input_tokens"] + total["output_tokens"]
    draws = ", ".join(f"{name[5:]} {len(entry['draws'])} of {DRAWS}"
                      for name, entry in manifest(root)["stages"].items()
                      if name.startswith(f"ch{n:02d}/") and entry["draws"])
    return (f"draws {draws}; {total['calls']} calls; {tokens} tokens (cached {total['cached_input_tokens']},"
            f" uncached {total['uncached_input_tokens']}, {total['unknown_usage_calls']} calls unknown);"
            f" {total['seconds']:.0f} s" + (f"; OVER {OVER_TOKENS}" if tokens > OVER_TOKENS else ""))


def ask(calls: Path, name: str, prompt: str, call, binary: Path) -> tuple[str, str]:
    """(answer, call folder). A completed receipt for this exact prompt is adopted without spending;
    a transport fault is retried at most RETRIES times and never counts as a draw."""
    attempts, suffix, fault = 0, 0, None
    while attempts <= RETRIES:
        directory, suffix = calls / (name if suffix == 0 else f"{name}r{suffix}"), suffix + 1
        if directory.exists():
            receipt = files.load(directory / "receipt.json") if (directory / "receipt.json").is_file() else {}
            final = directory / "final.md"
            if (receipt.get("status") == "completed" and final.is_file() and receipt.get("output_sha256")
                    == files.digest(final) and receipt.get("prompt_sha256") == files.sha(prompt.encode())):
                return files.read(final), directory.name
            continue
        attempts += 1
        try:
            answer, _ = call(prompt, directory, system=prompts.SYSTEM, model=MODEL, effort=EFFORT, binary=binary)
            return answer, directory.name
        except transport.Fault as error:
            fault = error
    raise transport.Fault(f"{name}: the call and {RETRIES} retries failed: {fault}")


def locate(word: str, stage: str, parts: list[tuple[str, str, str]]) -> str | None:
    """Where our own request carries the money word the model returned (any listed form of it,
    so 'rents' in the brief locates 'rent'), as file:line, or None."""
    for _, source, body in parts:
        for number, line in enumerate(body.splitlines(), 1):
            if any(sent[:4] == word[:4] for sent, _ in checks.money(line, stage)):
                return f"{source}:{number}"
    return None


def stage(root: Path, n: int, name: str, template: str, parts: list[tuple[str, str, str]], check,
          call, binary: Path) -> str:
    """Draw until the output passes its hard checks: at most DRAWS per input set, numbered on."""
    rendered = template.format(n=n, words=files.load(root / "serial.json")["words"])
    prompt = rendered + "".join(f"\n{prompts.PARTS[label]}:\n{body.strip()}\n" for label, _, body in parts)
    if len(prompt) > MAX_REQUEST:
        raise ValueError(f"ch{n:02d} {name}: the request is {len(prompt)} characters, over {MAX_REQUEST}")
    sent = {f"prompts.{name}": files.sha(rendered.encode()), "prompts.SYSTEM": files.sha(prompts.SYSTEM.encode()),
            **{source: files.sha(body.encode()) for _, source, body in parts}}
    key, record = files.sha(repr(sorted(sent.items())).encode()), manifest(root)
    entry = record["stages"].setdefault(f"ch{n:02d}/{name}", {"draws": []})
    same = [draw for draw in entry["draws"] if draw["inputs"] == key]
    calls = root / f"ch{n:02d}" / "calls"
    if same and not same[-1]["fails"]:
        return files.read(calls / same[-1]["dir"] / "final.md")
    while len(same) < DRAWS and not (same and same[-1]["located"]):
        k = len(entry["draws"]) + 1
        print(f"ch{n:02d} {name}: draw {len(same) + 1} of {DRAWS}", flush=True)
        output, directory = ask(calls, f"{name}-d{k}", prompt, call, binary)
        fails = check(output)
        words = [fail.split("'")[1] for fail in fails if fail.startswith("money: ")]
        places = [f"'{w}' in {place}" for w in words if (place := locate(
            w, "pitch" if name == "pitch" else "chapter", [("", f"prompts.{name.upper()}", rendered), *parts]))]
        same.append({"k": k, "dir": directory, "inputs": key, "sent": sent, "fails": fails,
                     "located": places[0] if places else None})
        entry["draws"].append(same[-1])
        files.save(root / "manifest.json", record)
        if not fails:
            return output
    last = same[-1]
    where = f"located in our request: {last['located']}" if last["located"] else f"{len(same)} draws failed"
    raise Stop(f"ch{n:02d} {name}: {where}\n  " + "\n  ".join(last["fails"]))


def new(slug: str, brief_file: Path, words: int, binary: Path, version: str, call=transport.codex) -> Path:
    """Create the serial and draw its pitch (bible and start sheet) for the operator's glance."""
    root, brief = folder(slug), files.read(brief_file)
    if not brief.strip() or tells.words(brief) > BRIEF_WORDS or not 500 <= words <= 5000:
        raise ValueError(f"A brief is 1-{BRIEF_WORDS} words and a chapter 500-5000 words")
    if not (root / "serial.json").is_file():
        root.mkdir(parents=True, exist_ok=True)
        keep(root, "brief.md", brief)
        files.save(root / "serial.json", {"words": words, "model": MODEL, "effort": EFFORT, "cli": version,
                                          "repo": files.revision(), "brief": files.sha(brief.encode())})
    elif files.load(root / "serial.json")["brief"] != files.sha(brief.encode()):
        raise Stop(f"{slug} exists with a different brief; edit its brief.md, or choose another slug")
    if not (root / "ch00" / "bible.md").is_file():
        bible = stage(root, 0, "pitch", prompts.PITCH, [("brief", "brief.md", text(root, "brief.md"))],
                      lambda out: checks.hard("pitch", out), call, binary)
        keep(root, "ch00/sheet.txt", sheet.render(sheet.start(checks.section(bible, "System") or "")))
        keep(root, "ch00/bible.md", bible)
    return root / "ch00" / "bible.md"


def chapter(root: Path, n: int, call, binary: Path) -> Path:
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
                       lambda out: checks.hard("plan", out, n=n, ranks=ranks), call, binary)
        keep(root, f"{here}/state.md", checks.split(output)[0])
        keep(root, f"{here}/plan.md", checks.split(output)[1])
    plan = text(root, f"{here}/plan.md")
    rise_plan = checks.planned(plan)
    if not (root / here / "chapter.md").is_file():
        parts = base + [("state", f"{here}/state.md", text(root, f"{here}/state.md")),
                        ("plan", f"{here}/plan.md", plan)] + previous
        raw = stage(root, n, "draft", prompts.DRAFT, parts, lambda out: checks.hard(
            "chapter", checks.normalize(out)[0], raw=out, target=target, n=n, before=before, ranks=ranks,
            rise_plan=rise_plan), call, binary)
        files.write(root / here / "final.md", raw)
        keep(root, f"{here}/chapter.md", checks.normalize(raw)[0])
    fixes = rewrite(root, n, call, binary)
    body, raw = text(root, f"{here}/chapter.md"), text(root, f"{here}/final.md")
    keep(root, f"{here}/sheet.txt", sheet.render(sheet.replay(before, body, ranks)[0]))
    files.write(root / here / "report.md", f"# {checks.title(plan, 'plan')}\n\n" + checks.report(
        body, raw=raw, target=target, n=n, plan=plan, bible=bible, before=before, ranks=ranks,
        fixes=fixes, usage=usage(root, n), normalized=checks.normalize(raw)[1]))
    return root / here / "report.md"


def rewrite(root: Path, n: int, call, binary: Path) -> list[tuple[str, str]]:
    """When 2 or more tell families run over their ceilings, one call says the located sentences
    again. A rewrite is kept only if it clears the counter and the money, leak and person checks.
    The kept pairs are recorded before chapter.md changes, so a resumed run re-applies, never re-asks."""
    record, name, body = manifest(root), f"ch{n:02d}/rewrite", text(root, f"ch{n:02d}/chapter.md")
    if name not in record["stages"]:
        located, over = tells.locate(body), tells.over(body)
        wanted = list(dict.fromkeys(s for family in over for s in located[family])) if len(over) >= 2 else []
        told, fixes = tells.sentences(body), []
        lines = [prompts.REWRITE_LINE.format(i=i, ask=prompts.ASKS[next(f for f in over if s in located[f])],
                                             before=told[told.index(s) - 1] if told.index(s) > 0 else "-", sentence=s)
                 for i, s in enumerate(wanted, 1)]
        request = prompts.REWRITE + "\n".join(lines) + "\n"
        answer = ask(root / f"ch{n:02d}" / "calls", "rewrite-d1", request, call, binary)[0] if wanted else ""
        for number, new in re.findall(r"^[ \t]*(\d+)\.[ \t]+(.+?)[ \t]*$", answer, re.M):
            old = wanted[int(number) - 1] if 0 < int(number) <= len(wanted) else ""
            if (old and old in body and not any(tells.locate(new)[f] for f in tells.CEILINGS)
                    and not (checks.money(new, "chapter") or checks.leak(new) or checks.person(new))):
                fixes.append((old, new))
        record["stages"][name] = {"draws": [], "fixes": fixes}
        files.save(root / "manifest.json", record)
    fixes, changed = [tuple(fix) for fix in record["stages"][name]["fixes"]], body
    for old, new in fixes:
        changed = changed.replace(old, new, 1)
    if changed != body:
        keep(root, f"ch{n:02d}/chapter.md", changed)
    return fixes


def next_chapters(slug: str, count: int, binary: Path, call=transport.codex) -> list[Path]:
    root = folder(slug)
    if not (root / "ch00" / "bible.md").is_file():
        raise Stop(f"{slug} has no pitch yet; run: new {slug} --brief FILE")
    if not 1 <= count <= MAX_CHAPTERS:
        raise ValueError(f"-n is 1 to {MAX_CHAPTERS}")
    return [chapter(root, done(root) + 1, call, binary) for _ in range(count)]


def redraw(slug: str, start: int) -> Path:
    """Move chapter `start` and every later one (0: the pitch too) to attempts/<utc>/. Nothing is deleted."""
    root = folder(slug)
    moving = [p for p in sorted(root.glob("ch[0-9][0-9]")) if int(p.name[2:]) >= start]
    if not moving:
        raise Stop(f"{slug} has nothing at or after ch{start:02d}")
    aside, record = root / "attempts" / files.utc(), manifest(root)
    aside.mkdir(parents=True)
    files.save(aside / "manifest.json", record)
    for path in moving:
        path.rename(aside / path.name)
    record["stages"] = {k: v for k, v in record["stages"].items() if int(k[2:4]) < start}
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
            if entry["draws"] and entry["draws"][-1]["fails"]:
                out += [f"  {name}: draw {len(entry['draws'])} failed" + (f", located in our request: "
                        f"{entry['draws'][-1]['located']}" if entry["draws"][-1]["located"] else "")]
                out += [f"    {fail}" for fail in entry["draws"][-1]["fails"]]
        out += [f"  hand-edited: {name}" for name, sha in record["files"].items()
                if (root / name).is_file() and files.digest(root / name) != sha]
        out += [f"  lock held: {text(root, 'lock/holder').strip()}"] * (root / "lock").exists()
        step = f"next {root.name}" if (root / "ch00" / "bible.md").is_file() else f"new {root.name} --brief FILE"
        out.append(f"  next: python -m litharness {step}")
    return "\n".join(out) or f"no serials under {files.home() / 'serials'}"
