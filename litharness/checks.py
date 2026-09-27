"""Deterministic checks. Hard checks can redraw a stage; reports never block and never reach a model."""
from __future__ import annotations

from collections import Counter
import re

from . import sheet, tells

MONEY_WORDS = (
    "rent", "rents", "rented", "renting", "rental", "landlords?", "tenants?", "leases?", "mortgages?",
    "bills", r"wages?(?!\s+(?:a\s+|the\s+|his\s+|their\s+)?(?:wars?|battles?|campaigns?)\b)",
    "salary", "salaries", "paychecks?", "payday", "payments?", "debts?", "owe", "owes", "owed", "owing",
    "loans?", "ledgers?", "invoices?", "overdraft", "budgets?", "repay", "creditors?", "licences?",
    "licenses?", "unpaid", "obligations?", "currency")
INSTITUTIONAL = ("courts?", "clerks?", "council", "probation", "inspect", "inspection", "inspector",
                 "paperwork", "permits?", "contracts?", "deeds?", "tax", "money")
ADMIN_WORDS = ("court", "clerk", "council", "inspection", "probation", "paperwork", "permit",
               "contract", "deed", "tax", "paid", "price", "coin", "cash", "bank", "money")
LABELS = ("Title", "Rise", "Ladder", "Start", "Age", "Listing", "Person", "Exception", "First use",
          "Threat", "Prize", "People", "Limits", "Where", "Held", "Open", "So far", "Opening",
          "Movements", "Options", "Ending")
COUNTS = r"(?:\d+|[IVX]+|One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten)"
BIBLE = ("Listing", "Person", "Exception", "First use", "Threat", "Prize", "System", "People", "Limits")
STATE, PLAN = ("Where", "Held", "Open", "So far"), ("Opening", "Movements", "Options", "People", "Ending")


def lexicon(*words: str) -> re.Pattern[str]:
    return re.compile(r"\b(?:" + "|".join(words) + r")\b", re.I)


MONEY, PITCH_MONEY, ADMIN = lexicon(*MONEY_WORDS), lexicon(*MONEY_WORDS, *INSTITUTIONAL), lexicon(*ADMIN_WORDS)
LEAK = re.compile(rf"^[ \t]*(?:#.*|={{3,}}.*|(?:{'|'.join(LABELS)})[ \t]*:.*)$|\b(?:Chapter|Scene)[ \t]+{COUNTS}\b", re.M)
SCHEMA = re.compile(r"\b(?:Ladder|Rung|Sheet|Standing|Listing|Prize|Exception)\b")
FIRST = re.compile(r"\b(?:I|[Mm]e|[Mm]y|[Mm]ine|[Mm]yself|[Ww]e|[Uu]s|[Oo]ur|[Oo]urs|[Oo]urselves)\b")
RISE = re.compile(r"^[ \t*]*Rise\**[ \t]*:[ \t]*(.+?)[ \t]*:[ \t]*(.+?)[ \t]*(?:->|→)[ \t]*(.+?)[ \t]*\|"
                  r"[ \t]*movement[ \t]*(\d+)[ \t]*\|[ \t]*(.*?)[ \t]*$", re.M | re.I)
NUMBERS = lexicon(r"\d[\d,.]*", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
                  "ten", "eleven", "twelve", "twenty", "thirty", "forty", "fifty", "hundred", "thousand")


def around(text: str, start: int, end: int) -> str:
    """The sentence (or line) holding text[start:end], on one line."""
    left = max(text.rfind(mark, 0, start) for mark in ".!?\n") + 1
    ends = [i for i in (text.find(mark, end) for mark in ".!?\n") if i >= 0]
    return " ".join(text[left:min(ends, default=len(text)) + 1].split())


def hits(pattern: re.Pattern[str], text: str) -> list[tuple[str, str]]:
    return [(m.group().lower(), around(text, m.start(), m.end())) for m in pattern.finditer(text)]


def money(text: str, stage: str) -> list[tuple[str, str]]:
    return hits(PITCH_MONEY if stage == "pitch" else MONEY, text)


def section(text: str, name: str) -> str | None:
    found = re.search(rf"^##[ \t]*{re.escape(name)}[ \t]*:?[ \t]*$(.*?)(?=^#|^===|\Z)", text, re.M | re.S | re.I)
    return found[1].strip() if found else None


def items(body: str) -> int:
    marked = re.findall(r"^[ \t]*(?:[-*]|\d+[.)])[ \t]+\S", body, re.M)
    return len(marked) or len([line for line in body.splitlines() if line.strip()])


def title(text: str, stage: str) -> str:
    found = re.search(r"^#[ \t]+(.+)$" if stage == "pitch" else r"^[ \t*]*Title\**[ \t]*:[ \t]*(.+)$", text, re.M)
    return found[1].strip(" *") if found else ""


def leak(text: str, whole_title: bool = False) -> list[str]:
    found = [m.group().strip() for m in LEAK.finditer(text)]
    for m in SCHEMA.finditer(text):
        before = text[:m.start()].rstrip(" \t\"“‘'*_")
        if whole_title or (before and before[-1] not in ".!?\n"):
            found.append(around(text, m.start(), m.end()))
    return [f"leak: {quote}" for quote in found]


def person(raw: str) -> list[str]:
    told = tells.narration(raw)
    rate = 1000 * len(FIRST.findall(told)) / max(tells.words(raw), 1)
    quotes = [s for s in tells.sentences(told) if FIRST.search(s)][:3]
    return [f"person: {rate:.1f} first-person words per 1k in narration: {' | '.join(quotes)}"] if rate > 2 else []


def planned(plan: str) -> tuple[str, ...] | None:
    found = RISE.search(plan)
    return found.groups() if found else None


def first_rise(events: list[tuple], known: bool) -> int | None:
    return next((e[4] for e in events if e[0] == "rise" or (known and e[0] == "new")), None)


def rise(chapter: str, n: int, before: dict, ranks: list[str], rise_plan=None) -> list[str]:
    fails, (_, events) = [], sheet.replay(before, chapter, ranks)
    if rise_plan:
        label, _, new, *_ = rise_plan
        target = sheet.value(new, ranks)
        if not any(sheet.key(f[0]) == sheet.key(label) and sheet.value(f[1], ranks) == target
                   for f in sheet.fields(chapter)):
            fails.append(f"rise: the planned [{label}: {new}] is not printed")
    if n == 1:
        first = first_rise(events, bool(before))
        if not sheet.STATUS.search(chapter):
            fails.append("rise: chapter 1 has no status line")
        elif first is None or tells.words(chapter[:first]) > tells.words(chapter) / 2:
            fails.append("rise: chapter 1's first rise is missing or after the word midpoint")
    return fails


def bad(label: str, raw: str, ranks: list[str], known: bool) -> str | None:
    parsed = sheet.value(raw, ranks)
    if parsed is None:
        return f"[{label}: {raw}] does not parse" if known else None
    number, size = parsed
    if size is None:
        return f"[{label}: {raw}] is at 0" if number == 0 else None
    return f"[{label}: {raw}] is not a pool n/m with m >= 1 and n <= m" if size < 1 or number > size else None


def fields(text: str, before: dict, ranks: list[str]) -> list[str]:
    known, fails = {sheet.key(label) for label in before}, []
    for label, raw, _ in sheet.fields(text):
        problem = bad(label, raw, ranks, sheet.key(label) in known)
        fails += [f"fields: {problem}"] if problem else []
        if sheet.value(raw, ranks) is not None:
            known.add(sheet.key(label))
    return fails + ([f"fields: {len(known)} labels would pass the {sheet.CAP}-line sheet"] if len(known) > sheet.CAP else [])


def pitch_shape(bible: str) -> list[str]:
    fails = [f"'## {name}' is missing or empty" for name in BIBLE if not section(bible, name)]
    age = re.search(r"Age\**[ \t]*:[ \t*]*(\d+)", section(bible, "Person") or "", re.I)
    system, listing = section(bible, "System") or "", tells.sentences(section(bible, "Listing") or "")
    starts = sheet.start(system)
    fails += ["no '# Title' line"] * (not title(bible, "pitch"))
    fails += ["Age is not 20-29"] * (not age or not 20 <= int(age[1]) <= 29)
    fails += ["Ladder names fewer than 3 ranks"] * (len(sheet.ladder(system)) < 3)
    fails += [f"Start has {len(starts)} fields, not 1-6"] * (not 1 <= len(starts) <= 6)
    fails += [f"Start {problem}" for problem in (bad(k, v, sheet.ladder(system), True) for k, v in starts.items()) if problem]
    fails += ["People names more than 3"] * (items(section(bible, "People") or "") > 3)
    fails += ["Listing runs past 3 sentences or 27 words in one"] * (len(listing) > 3 or any(tells.words(s) > 27 for s in listing))
    fails += [f"bible is {tells.words(bible)} words, over 900"] * (tells.words(bible) > 900)
    return [f"pitch-shape: {problem}" for problem in fails]


def split(output: str) -> tuple[str, str] | None:
    parts = re.split(r"^[ \t]*===[ \t]*(STATE|PLAN)[ \t]*===[ \t]*$", output, flags=re.M)
    return (parts[2].strip() + "\n", parts[4].strip() + "\n") if parts[1::2] == ["STATE", "PLAN"] else None


def plan_shape(output: str, n: int, ranks: list[str]) -> list[str]:
    halves = split(output)
    if not halves:
        return ["plan-shape: needs '=== STATE ===' then '=== PLAN ===', once each"]
    state, plan = halves
    fails = [f"'## {h}' missing" for h, part in [*((h, state) for h in STATE), *((h, plan) for h in PLAN)]
             if section(part, h) is None]
    rise_plan, moves = planned(plan), re.findall(r"^[ \t]*\d+[.)][ \t]+\S", section(plan, "Movements") or "", re.M)
    fails += ["no 'Title:' line"] * (not title(plan, "plan"))
    fails += [f"state is {tells.words(state)} words, over 600"] * (tells.words(state) > 600)
    fails += [f"plan is {tells.words(plan)} words, over 400"] * (tells.words(plan) > 400)
    fails += ["Open has more than 8 lines"] * (items(section(state, "Open") or "") > 8)
    fails += ["So far runs past 150 words"] * (tells.words(section(state, "So far") or "") > 150)
    fails += ["People names more than 4"] * (items(section(plan, "People") or "") > 4)
    fails += [f"Movements has {len(moves)} numbered movements, not 3"] * (len(moves) != 3)
    if not rise_plan or sheet.value(rise_plan[2], ranks) is None or not rise_plan[4]:
        fails.append("'Rise: Label: old -> new | movement k | the act' is missing, unparseable or lacks its act")
    elif n == 1 and rise_plan[3] != "1":
        fails.append("chapter 1's Rise is not in movement 1")
    return [f"plan-shape: {problem}" for problem in fails]


def length(chapter: str, target: int) -> list[str]:
    count = tells.words(chapter)
    return [f"length: {count} words for a {target}-word target"] if not 0.6 * target <= count <= 1.8 * target else []


def hard(stage: str, text: str, *, raw: str = "", target: int = 1500, n: int = 1, before=None,
         ranks=(), rise_plan=None) -> list[str]:
    """Every hard failure for one stage's output, each with its located quote."""
    before, ranks = before or {}, list(ranks)
    fails = [f"money: '{word}' in: {quote}" for word, quote in money(text, stage)]
    fails += leak(title(text, stage), whole_title=True) if stage != "chapter" else leak(text)
    if stage == "pitch":
        return fails + pitch_shape(text)
    if stage == "plan":
        return fails + plan_shape(text, n, ranks)
    return (fails + person(raw or text) + rise(text, n, before, ranks, rise_plan)
            + fields(text, before, ranks) + length(text, target))


def normalize(raw: str) -> tuple[str, dict]:
    """chapter.md from the raw draft: dashes to commas, a leading '# ' title lifted, breaks as ***."""
    body, counts = raw.replace("\r\n", "\n").strip(), {}
    body, counts["title"] = re.subn(r"\A#[ \t]+.*(?:\n|\Z)", "", body)
    body, closing = re.subn(r"[ \t]*[—–]+[ \t]*(?=[\"”’)]|$)", ",", body, flags=re.M)
    body, inner = re.subn(r"[ \t]*[—–]+[ \t]*", ", ", body)
    body, counts["breaks"] = re.subn(r"^[ \t]*(?:[*\-_~=][ \t]*){3,}$", "***", body, flags=re.M)
    body = re.sub(r"\*\*\*(?:\s*\n\s*\*\*\*)+", "***", body).strip()
    counts["dashes"] = closing + inner
    return re.sub(r"\A\*\*\*\s*|\s*\*\*\*\Z", "", body).strip() + "\n", counts


def rate(count: int, text: str) -> str:
    return f"{count} ({1000 * count / max(tells.words(text), 1):.1f}/1k)"


def report(chapter: str, *, raw: str = "", target: int = 1500, n: int = 1, plan: str = "", bible: str = "",
           before=None, ranks=(), fixes=(), usage: str = "", normalized: dict | None = None) -> str:
    """report.md: every inert report, located. It never blocks and never reaches a model."""
    before, ranks, count, out = before or {}, list(ranks), tells.words(chapter), []
    low, high = round(0.8 * target), round(4 * target / 3)
    out.append(f"- len-band: {count} words" + ("" if low <= count <= high else f", outside {low}-{high}"))
    for name, text in (("plan", plan), ("chapter", chapter)):
        found = hits(ADMIN, text)
        tally = ", ".join(f"{w} x{k}" for w, k in Counter(w for w, _ in found).most_common())
        out += [f"- admin ({name}): {rate(len(found), text)} {tally}"] + [f"  - {w}: {q}" for w, q in found[:6]]
    rates, located, shape = tells.rates(chapter), tells.locate(chapter), tells.shape(chapter)
    out.append("- tells: " + ", ".join(f"{f} {r:.1f}/{tells.CEILINGS[f]}" for f, r in rates.items())
               + f"; median sentence {shape['median']:.0f} words, under 4 words {shape['short_share']:.0%}")
    out += [f"  - {f}: {q}" for f in [*tells.over(chapter), "long"] for q in located[f][:4]]
    body = sheet.STATUS.sub("", chapter)
    numbers = hits(NUMBERS, body)
    out += [f"- digits: {rate(len(numbers), body)}"] + [f"  - {q}" for _, q in numbers[:3]]
    names = {}
    for m in re.finditer(r"\b[A-Z][a-z]+\b", body):
        if body[:m.start()].rstrip(" \t\"“‘'*_")[-1:] not in {"", ".", "!", "?", "\n"}:
            names[m.group()] = names.get(m.group(), 0) + 1
    cast = sorted(name for name, k in names.items() if k >= 2)
    out.append(f"- cast: {len(cast)} named{' (over 5)' if len(cast) > 5 else ''}: {', '.join(cast)}")
    if n == 1 and bible:
        person = section(bible, "Person") or ""
        name, age = re.search(r"[A-Z][a-z]+", person), re.search(r"Age\**[ \t]*:[ \t*]*(\d+)", person)
        units = "one two three four five six seven eight nine".split()
        spoken = f"twenty[- ]{units[int(age[1]) - 21]}" if age and 21 <= int(age[1]) <= 29 else "twenty"
        for what, pattern in (("name", name and name.group()), ("age", age and rf"{age[1]}|{spoken}")):
            found = bool(pattern) and re.search(rf"\b(?:{pattern})\b", chapter, re.I)
            out.append(f"- literals: {what} {'present' if found else 'MISSING'}")
        used = re.findall(r"(?<=[a-z,;] )[A-Z][a-z]+", section(bible, "First use") or "")
        out.append(f"- literals: first use terms on the page: {[u for u in used if u in chapter]} of {used}")
    after, events = sheet.replay(before, chapter, ranks)
    spellings = {}
    for label, _, _ in sheet.fields(chapter):
        spellings.setdefault(sheet.key(label), set()).add(label)
    first = first_rise(events, bool(before))
    out.append(f"- sheet: {sum(e[0] == 'rise' for e in events)} rises, first at word "
               f"{tells.words(chapter[:first]) if first is not None else 'none'}; {len(after)} labels")
    out += [f"  - fall: {e[1]} {e[2]} -> {e[3]}" for e in events if e[0] == "fall"]
    out += [f"  - new label: {e[1]} {e[3]}" for e in events if e[0] == "new"]
    out += [f"  - spelled {len(s)} ways: {sorted(s)}" for s in spellings.values() if len(s) > 1]
    out += [f"  - generic label: {label}" for label in after if sheet.key(label) in sheet.GENERIC]
    out += ["  - no status line"] * (not sheet.STATUS.search(chapter))
    told = tells.narration(raw or chapter)
    present = len(re.findall(r"\b(?:is|are|am)\b", told)), len(re.findall(r"\b(?:was|were)\b", told))
    out.append(f"- address: 'you' in narration {rate(len(re.findall(r'(?i)\byou\b', told)), chapter)}, "
               f"italics {rate(len(re.findall(r'(?<![*\w])\*[^*\n]+\*', raw or chapter)), chapter)}, "
               f"present tense {present[0] / max(sum(present), 1):.0%} of is/are/am/was/were")
    out += [f"- normalized: {normalized}"] * bool(normalized)
    out += [f"- rewrite: {old} => {new}" for old, new in fixes]
    out += [f"- usage: {usage}"] * bool(usage)
    return "\n".join(out) + "\n"
