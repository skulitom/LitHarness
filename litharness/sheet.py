"""The status sheet: `[Label: value]` lines he prints on the page, read back by code. Nothing is
extracted from prose. A value is a whole number, a Ladder name (its 1-based rank) or a pool n/m."""
from __future__ import annotations

import re

STATUS = re.compile(r"^[ \t]*\[([^\[\]\n]+)\][ \t\r]*$", re.M)
FIELD = re.compile(r"^\s*([^:\[\]]+?)\s*:\s*(\S.*?)\s*$")
POOL = re.compile(r"^(\d+)\s*/\s*(\d+)$")
GENERIC = {"hp", "mp", "gold", "xp"}
CAP = 12


def key(label: str) -> str:
    return re.sub(r"[^a-z0-9]", "", label.lower())


def ladder(bible: str) -> list[str]:
    """Rank names, lowest first: the Ladder line up to its first sentence end, parentheticals dropped."""
    found = re.search(r"\bLadder\**[ \t]*:[ \t]*(.+)$", bible, re.M | re.I)
    line = re.sub(r"\([^)]*\)", "", found[1]).split(". ")[0] if found else ""
    names = re.split(r"\s*(?:,|;|->|→|>|\|)\s*(?:(?:and|or|then)\s+)?|\s+(?:and|or|then)\s+", line)
    return [name.strip(" .*`") for name in names if name.strip(" .*`")]


def value(raw: str, ranks: list[str]) -> tuple[int, int | None] | None:
    """(number, pool size or None for a plain value), or None when it is not a value. An annotation after
    the value ('3, Holdfast, Gill', '3 (two active)') is the System's gloss, not part of the value."""
    raw = re.sub(r"(?<=\d),(?=\d{3}\b)", "", raw.strip().strip("*`"))
    raw = re.split(r"\s*(?:,\s|[—–(;]|\s-\s)", raw, maxsplit=1)[0].strip()
    pool = POOL.match(raw)
    if pool:
        return int(pool[1]), int(pool[2])
    if raw.isdecimal():
        return int(raw), None
    names = [key(name) for name in ranks]
    return (names.index(key(raw)) + 1, None) if key(raw) in names else None


def order(raw: str, ranks: list[str]) -> int | None:
    """What a rise compares: pools by their size, everything else by its number."""
    parsed = value(raw, ranks)
    return None if parsed is None else parsed[0] if parsed[1] is None else parsed[1]


def fields(text: str) -> list[tuple[str, str, int]]:
    """(label, raw value, offset) for every status line shaped Label: value, in page order."""
    return [(field[1], field[2], line.start()) for line in STATUS.finditer(text) if (field := FIELD.match(line[1]))]


def start(bible: str) -> dict[str, str]:
    """The bible's `Start:` fields, which become the chapter-0 sheet."""
    block = re.search(r"^[\s>*-]*\**Start\**\s*:(.*?)(?=^\s*#|^[ \t>*-]*[A-Za-z][\w ]*:|\Z)",
                      bible, re.M | re.S | re.I)
    pairs = [FIELD.match(inner) for inner in re.findall(r"\[([^\[\]\n]+)\]", block[1] if block else "")]
    return {pair[1]: pair[2] for pair in pairs if pair}


def read(text: str) -> dict[str, str]:
    return {label: raw for label, raw, _ in fields(text)}


def render(sheet: dict[str, str]) -> str:
    return "".join(f"[{label}: {raw}]\n" for label, raw in sheet.items())


def replay(sheet: dict[str, str], text: str, ranks: list[str]) -> tuple[dict[str, str], list[tuple]]:
    """Each label takes its last printed value. Events are (kind, label, old, new, offset) with kind
    rise, fall or new; a label printed unparseable stays a System notice and changes nothing."""
    current, events, names = dict(sheet), [], {key(label): label for label in sheet}
    for label, raw, offset in fields(text):
        now = order(raw, ranks)
        if now is None:
            continue
        name = names.setdefault(key(label), label)
        before = order(current[name], ranks) if name in current else None
        if name not in current:
            events.append(("new", name, None, raw, offset))
        elif now != before:
            events.append(("rise" if before is None or now > before else "fall", name, current[name], raw, offset))
        current[name] = raw
    return current, events
