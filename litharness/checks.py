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
INSTITUTIONAL = (r"(?<!ball )courts?", "clerks?", r"council(?!(?-i: [A-Z]))", "probation", "inspectors?", "paperwork",
                 r"contracts?(?! (?:around|until)\b)", "deeds?", "tax", "money")
ADMIN_WORDS = ("courts?", "clerks?", "council", "inspect", "inspections?", "inspectors?", "probation", "paperwork",
               "permits?", "contracts?", "deeds?", "tax", "paid", "prices?", "coins?", "cash", "banks?", "money")
LABELS = ("Title|Rise|Ladder|Start|Age|Listing|Person|Exception|First use|Threat|Prize|People|Limits|Where"
          "|Held|Open|So far|Opening|Movements|Options|Ending")
BIBLE = ("Listing", "Person", "Exception", "First use", "Threat", "Prize", "System", "People", "Limits")
STATE, PLAN = ("Where", "Held", "Open", "So far"), ("Opening", "Movements", "Options", "People", "Ending")


def lexicon(*words: str) -> re.Pattern[str]:
    return re.compile(r"\b(?:" + "|".join(words) + r")\b", re.I)


MONEY, PITCH_MONEY, ADMIN = lexicon(*MONEY_WORDS), lexicon(*MONEY_WORDS, *INSTITUTIONAL), lexicon(*ADMIN_WORDS)
LEAK = re.compile(rf"^[ \t>*_]*(?:#.*|={{3,}}.*|(?:{LABELS})[*_]*[ \t]*:.*)$|\b(?:Chapter|CHAPTER|Scene|SCENE)"
                  r"[ \t]+(?:\d+|[IVXL]+\b|(?i:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
                  r"|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty))\b", re.M)
SCHEMA = re.compile(r"\b(?:Ladder|Rung|Sheet|Listing|Prize|Exception)\b")
FIRST = re.compile(r"\b(?:I|[Mm]e|[Mm]y|[Mm]yself|[Ww]e|[Uu]s|[Oo]ur|[Oo]urs|[Oo]urselves)\b")
RISE = re.compile(r"^[ \t>*_-]*Rise\**[ \t]*:\**[ \t]*(.+?)[ \t]*:[ \t]*(.+?)[ \t]*(?:->|→)[ \t]*(.+?)[ \t]*\|"
                  r"[ \t]*movement[ \t]*(\d+)[ \t]*\|[ \t]*(.*?)[ \t]*$", re.M | re.I)
AGE, ROW = r"Age\**[ \t]*:[ \t*]*(\d+)", re.compile(r"^([ \t]*)((?:[-*]|\**\d+[.)])[ \t]+)?\S", re.M)


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
    found = re.search(rf"^##[ \t]*\**{re.escape(name)}\**[ \t]*:?[ \t]*$(.*?)(?=^#|^===|\Z)", text, re.M | re.S | re.I)
    return found[1].strip() if found else None


def items(body: str | None) -> int:
    """Entries of a list: unmarked lines heading their own markers, else markers at the outermost indent, else lines."""
    rows, marks = "".join("m" if m else "u" for _, m in ROW.findall(body or "")), [i for i, m in ROW.findall(body or "") if m]
    return rows.count("u") if re.match("u+m+u", rows) else marks.count(min(marks, key=len)) if marks else len(rows)


def title(text: str, stage: str) -> str:
    found = re.search(r"^#[ \t]+(.+)$" if stage == "pitch" else r"^[ \t>*_-]*(?:#+[ \t]*)?Title\**[ \t]*:\**[ \t]*(.+)$",
                      text, re.M)
    return found[1].strip(" *") if found else ""


def initial(text: str, start: int) -> bool:
    """Whether text[start:] opens a sentence or a quoted speech."""
    before = text[:start].rstrip(" \t*_")
    opened, before = before[-1:] in {'"', "“", "‘", "'"}, before.rstrip(" \t*_\"“”‘’'")
    return before[-1:] in {"", ".", "!", "?", "…", "\n"} or (opened and before[-1:] in {",", ":"})


def leak(text: str, whole_title: bool = False, brief: str = "") -> list[str]:
    found = [m.group().strip() for m in LEAK.finditer(text)] + [around(text, m.start(), m.end()) for m in SCHEMA.finditer(text)
             if (whole_title or not initial(text, m.start())) and m.group().lower() not in brief.lower()]
    return [f"leak: {quote}" for quote in found]


def person(raw: str) -> list[str]:
    """First-person narration; an I closing a mid-sentence Title Case run (Tier I, Hold Breath I) is a numeral."""
    told = tells.narration(raw)
    found = [m for m in FIRST.finditer(told)
             if m.group() != "I" or not re.search(r"[a-z,;] [A-Z]\w* $", told[max(0, m.start() - 60):m.start()])]
    rate = 1000 * len(found) / max(tells.words(raw), 1)
    quotes = " | ".join(dict.fromkeys(around(told, m.start(), m.end()) for m in found[:6]))
    return [f"person: {rate:.1f} first-person words per 1k in narration: {quotes}"] if rate > 2 else []


def planned(plan: str) -> tuple[str, ...] | None:
    found = RISE.search(plan)
    return found.groups() if found else None


def first_rise(events: list[tuple], known: bool) -> int | None:
    return next((e[4] for e in events if e[0] == "rise" or (known and e[0] == "new")), None)


def rise(chapter: str, n: int, before: dict, ranks: list[str], rise_plan=None) -> list[str]:
    """The planned label rises to its planned value on the page (pools by their size); in chapter 1 that
    rise, or without a plan the first rise, comes before the word midpoint."""
    events, fails = sheet.replay(before, chapter, ranks)[1], []
    first = first_rise(events, bool(before))
    if rise_plan:
        first = next((e[4] for e in events if e[0] in {"rise", "new"} and sheet.key(e[1]) == sheet.key(rise_plan[0])
                      and sheet.order(e[3], ranks) == sheet.order(rise_plan[2], ranks)), None)
        fails += [f"rise: the planned [{rise_plan[0]}: {rise_plan[2]}] is not printed as a rise"] * (first is None)
    if n == 1 and not sheet.STATUS.search(chapter):
        fails.append("rise: chapter 1 has no status line")
    elif n == 1 and (first is None or tells.words(chapter[:first]) > tells.words(chapter) / 2) and not fails:
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


def fields(text: str, before: dict, ranks: list[str], rise_plan=None) -> list[str]:
    """Status fields that break the sheet; the planned Rise may show its old value, even a 0 it rises from."""
    known, fails = {sheet.key(label) for label in before}, []
    for label, raw, _ in sheet.fields(text):
        if rise_plan and sheet.key(label) == sheet.key(rise_plan[0]) and raw.strip() == rise_plan[1].strip():
            continue
        fails += [f"fields: {problem}"] if (problem := bad(label, raw, ranks, sheet.key(label) in known)) else []
        known |= {sheet.key(label)} if sheet.value(raw, ranks) is not None else set()
    return fails + [f"fields: {len(known)} labels would pass the {sheet.CAP}-line sheet"] * (len(known) > sheet.CAP)


def pitch_shape(bible: str) -> list[str]:
    age = re.search(AGE, section(bible, "Person") or "", re.I)
    system, listing = section(bible, "System") or "", tells.sentences(section(bible, "Listing") or "")
    starts, ranks = sheet.start(system), sheet.ladder(system)
    fails = [f"'## {name}' is missing or empty" for name in BIBLE if not section(bible, name)]
    fails += ["no '# Title' line"] * (not title(bible, "pitch"))
    fails += ["Age is not 20-29"] * (not age or not 20 <= int(age[1]) <= 29)
    fails += ["Ladder names fewer than 3 ranks"] * (len(ranks) < 3)
    fails += [f"Start has {len(starts)} fields, not 1-6"] * (not 1 <= len(starts) <= 6)
    fails += [f"Start {problem}" for key, raw in starts.items() if (problem := bad(key, raw, ranks, True))]
    fails += ["People names more than 3"] * (items(section(bible, "People")) > 3)
    fails += ["Listing runs past 3 sentences or 27 words in one"] * (len(listing) > 3 or any(
        tells.words(s) > 27 for s in listing))
    fails += [f"bible is {tells.words(bible)} words, over 900"] * (tells.words(bible) > 900)
    return [f"pitch-shape: {problem}" for problem in fails]


def split(output: str) -> tuple[str, str] | None:
    parts = re.split(r"^[ \t]*===[ \t]*(STATE|PLAN)[ \t]*===[ \t]*$", output, flags=re.M)
    return (parts[2].strip() + "\n", parts[4].strip() + "\n") if parts[1::2] == ["STATE", "PLAN"] else None


def plan_shape(output: str, n: int, ranks: list[str], before: dict | None = None) -> list[str]:
    if not (halves := split(output)):
        return ["plan-shape: needs '=== STATE ===' then '=== PLAN ===', once each"]
    (state, plan), rise_plan, before = halves, planned(halves[1]), before or {}
    moves = re.findall(r"^[ \t]*\**\d+[.)]\**[ \t]+\S", section(plan, "Movements") or "", re.M)
    fails = [f"'## {h}' missing" for part, names in ((state, STATE), (plan, PLAN)) for h in names
             if section(part, h) is None]
    fails += ["no 'Title:' line"] * (not title(plan, "plan"))
    fails += [f"state is {tells.words(state)} words, over 600"] * (tells.words(state) > 600)
    fails += [f"plan is {tells.words(plan)} words, over 400"] * (tells.words(plan) > 400)
    fails += ["Open has more than 8 lines"] * (items(section(state, "Open")) > 8)
    fails += ["So far runs past 150 words"] * (tells.words(section(state, "So far") or "") > 150)
    fails += ["People names more than 4"] * (items(section(plan, "People")) > 4)
    fails += [f"Movements has {len(moves)} numbered movements, not 3"] * (len(moves) != 3)
    if not rise_plan or (ranks and sheet.value(rise_plan[2], ranks) is None) or not rise_plan[4]:
        fails.append("'Rise: Label: old -> new | movement k | the act' is missing, unparseable or lacks its act")
    elif n == 1 and rise_plan[3] != "1":
        fails.append("chapter 1's Rise is not in movement 1")
    elif before and sheet.key(rise_plan[0]) not in {sheet.key(label) for label in before} and sheet.order(
            rise_plan[1], ranks):
        fails.append(f"the Rise label {rise_plan[0]} is not on the sheet, and {rise_plan[1]} is not a new label's 0")
    elif (new := sheet.order(rise_plan[2], ranks)) is not None and new <= (sheet.order(rise_plan[1], ranks) or 0):
        fails.append(f"the Rise {rise_plan[1]} -> {rise_plan[2]} does not rise")
    return [f"plan-shape: {problem}" for problem in fails]


def length(chapter: str, target: int) -> list[str]:
    count = tells.words(chapter)
    return [f"length: {count} words for a {target}-word target"] if not 0.6 * target <= count <= 1.8 * target else []


def hard(stage: str, text: str, *, raw: str = "", target: int = 1500, n: int = 1, before=None,
         ranks=(), rise_plan=None, brief: str = "") -> list[str]:
    """Every hard failure for one stage's output, each with its located quote; a title may echo the brief's words."""
    before, ranks = before or {}, list(ranks)
    fails = [f"money: '{word}' in: {quote}" for word, quote in money(text, stage)]
    fails += leak(title(text, stage), whole_title=True, brief=brief) if stage != "chapter" else leak(text)
    if stage != "chapter":
        return fails + (pitch_shape(text) if stage == "pitch" else plan_shape(text, n, ranks, before))
    return (fails + person(raw or text) + rise(text, n, before, ranks, rise_plan)
            + fields(text, before, ranks, rise_plan) + length(text, target))


def normalize(raw: str) -> tuple[str, dict]:
    """chapter.md from the raw draft: dashes to commas, a leading '# ' title lifted, breaks as ***."""
    body, counts = raw.replace("\r\n", "\n").strip(), {}
    body, counts["title"] = re.subn(r"\A#[ \t]+.*(?:\n|\Z)", "", body)
    body, closing = re.subn(r"[ \t]*[—–]+[ \t]*(?=[\"”’)*_]|$)", ",", body, flags=re.M)
    body, inner = re.subn(r"[ \t]*[—–]+[ \t]*", ", ", body)
    body, counts["breaks"] = re.subn(r"^[ \t]*(?:[*\-_~=][ \t]*){3,}$", "***", body, flags=re.M)
    body, counts["dashes"] = re.sub(r"\*\*\*(?:\s*\n\s*\*\*\*)+", "***", body).strip(), closing + inner
    return re.sub(r"\A\*\*\*\s*|\s*\*\*\*\Z", "", body).strip() + "\n", counts


def rate(count: int, text: str) -> str:
    return f"{count} ({1000 * count / max(tells.words(text), 1):.1f}/1k)"


def report(chapter: str, *, raw: str = "", target: int = 1500, n: int = 1, plan: str = "", bible: str = "",
           before=None, ranks=(), fixes=(), usage: str = "", normalized: dict | None = None) -> str:
    """report.md: every inert report, located. It never blocks and never reaches a model."""
    before, ranks, count = before or {}, list(ranks), tells.words(chapter)
    low, high = round(0.8 * target), round(4 * target / 3)
    out = [f"- len-band: {count} words" + ("" if low <= count <= high else f", outside {low}-{high}")]
    for name, text in (("plan", plan), ("chapter", chapter)) if plan else (("chapter", chapter),):
        found = hits(ADMIN, text)
        tally = ", ".join(f"{w} x{k}" for w, k in Counter(w for w, _ in found).most_common())
        out += [f"- admin ({name}): {rate(len(found), text)} {tally}"] + [f"  - {w}: {q}" for w, q in found[:6]]
    rates, located, shape = tells.rates(chapter), tells.locate(chapter), tells.shape(chapter)
    out.append("- tells: " + ", ".join(f"{f} {r:.1f}/{tells.CEILINGS[f]}" for f, r in rates.items())
               + f"; median sentence {shape['median']:.0f} words, under 4 words {shape['short_share']:.0%}")
    out += [f"  - {f}: {q}" for f in [*tells.over(chapter), "long"] for q in located[f][:4]]
    if n == 1 and bible:
        person, used = section(bible, "Person") or "", re.findall(r"(?<=[a-z,;] )[A-Z][a-z]+", section(bible, "First use") or "")
        name = re.search(r"[A-Z][a-z]+", re.sub(r"^\W*(?:His\s+)?name\W*", "", person, flags=re.I))
        age = re.search(AGE, person)
        units = ["", "[- ]one", "[- ]two", "[- ]three", "[- ]four", "[- ]five", "[- ]six", "[- ]seven", "[- ]eight", "[- ]nine"]
        spoken = age and 20 <= int(age[1]) <= 29 and rf"{age[1]}|twenty{units[int(age[1]) - 20]}"
        for what, pattern in (("name", name and name.group()), ("age", spoken or (age and age[1]))):
            seen = bool(pattern and re.search(rf"\b(?:{pattern})\b", chapter, re.I))
            out.append(f"- literals: {what} {'present' if seen else 'MISSING'}")
        out.append(f"- literals: first use terms on the page: {[u for u in used if u in chapter]} of {used}")
    after, events = sheet.replay(before, chapter, ranks)
    spellings, first = {}, first_rise(events, bool(before))
    for label, _, _ in sheet.fields(chapter):
        spellings.setdefault(sheet.key(label), set()).add(label)
    out.append(f"- sheet: {sum(e[0] == 'rise' for e in events)} rises, first at word "
               f"{tells.words(chapter[:first]) if first is not None else 'none'}; {len(after)} labels")
    planned_key = sheet.key((planned(plan) or ("",))[0])
    out += [f"  - {e[0]} {e[1]}: {e[2] + ' -> ' if e[2] else ''}{e[3]}" for e in events
            if e[0] == "fall" or (e[0] == "new" and sheet.key(e[1]) != planned_key)]
    out += [f"  - spelled {len(s)} ways: {sorted(s)}" for s in spellings.values() if len(s) > 1]
    out += [f"  - generic label: {label}" for label in after if sheet.key(label) in sheet.GENERIC]
    out += ["  - no status line"] * (not sheet.STATUS.search(chapter))
    out += [f"- normalized: {normalized}"] * bool(normalized)
    out += [f"- rewrite: {old} => {new}" for old, new in fixes] + [f"- usage: {usage}"] * bool(usage)
    return "\n".join(out) + "\n"
