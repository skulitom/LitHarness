"""Where our chapters sit among RoyalRoad LitRPG titles at the same chapter, measured by code alone.

    python bench.py baseline SLUG   writes $LITHARNESS_HOME/serials/SLUG/baseline/<utc>.md and .json

A description, never a verdict: no model call, no bar; nothing here reaches a model or decides a redraw.
The genre corpus (experiments/2026-09-28-genre-baseline/) lives outside the repo, and reports carry numbers,
fiction ids and our own line numbers, never genre text. The same normalize() and counters run on both halves.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import statistics
import sys
import unicodedata

from litharness import checks, files

VERSION = "genre_census.v1"
ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "experiments" / "2026-09-28-genre-baseline" / "manifest.json"
CORPUS, INCUMBENT = files.home() / "corpora" / "genre", Path("C:/DEV/LitHarness-archive/tree/book-library")
BR, AN = re.compile(r"^\[[^\]]{1,200}\][.!?]?$"), re.compile(r"^<[^>]{1,200}>[.!?]?$")
TAGGED = re.compile(r"^\[[A-Za-z][A-Za-z ]{1,23}\]\s*\S.{0,160}$")
STAT = re.compile(r"^[A-Za-z][A-Za-z '/()-]{0,28}\s*:\s*[^.!?\n]{0,40}\d[^.!?\n]{0,40}$")
REJ = re.compile(r"^[\[<]?\s*(?:a/?n|author'?s? note|t/?n|translator|tl|edit|note|p\.?s\.?|prev(?:ious)?|next|table of "
                 r"contents|toc|index|chapter\s+\d|patreon|discord|advance chapters?|support|donate|vote|rating|spoiler|"
                 r"image|img|picture)\b", re.I)
FIELD = re.compile(r"^\[?\s*([A-Za-z][A-Za-z '/()-]{0,28}?)\s*:\s*(\d[\d,]*)(?:\s*/\s*(\d[\d,]*))?")
LVL = re.compile(r"\b(?:level(?:l?ed)?[\s-]?up|levels?\s+up|rank(?:ed)?[\s-]?up|class\s+change|evolv(?:ed|es|ing)\s+into|"
                 r"advanc(?:ed|es)\s+to|promoted\s+to|ascend(?:ed|s)\s+to|brok\w*\s+through\s+to|reached\s+(?:level|rank|"
                 r"tier|stage|grade)|now\s+(?:a\s+|an\s+)?(?:level|rank|tier)\s)\b", re.I)
CAP = re.compile(r"\b(?:learn(?:ed|t)|acquired|obtained|unlocked|gained|received|awakened|mastered)\b[^.!?\n]{0,40}?"
                 r"\b(?:skill|ability|spell|technique|title|perk|trait|class|feat|talent|power|art)s?\b|\bnew\s+(?:skill|"
                 r"ability|spell|title|perk|class|technique|power)s?\b", re.I)
DELTA = re.compile(r"\b\d[\d,]*\s*(?:->|=>)\s*\d[\d,]*\b|(?<![\w.])\+\s?\d[\d,]*\b|\b(?:gain(?:ed|s)?|earn(?:ed|s)?|"
                   r"receiv(?:ed|es)|award(?:ed|s)?)\b[^.!?\n]{0,30}?\b\d[\d,]*\s*(?:xp|exp|experience|mana|gold|coins?|"
                   r"credits?|points?|levels?|stat\s+points?)\b", re.I)
SENT, WORD = re.compile(r"[^.!?]+[.!?]+[\"')\]]*|[^.!?]+$"), re.compile(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*")
LEXICON = {
    "inter": r"thought|wondered|reali[sz]ed|knew|felt|remembered|wanted|hoped|feared|wished|decided|guessed|supposed|"
             r"imagined|considered|worried|suspected|believed|understood",
    "viol": r"attack\w*|strik\w*|struck|slash\w*|stab\w*|punch\w*|kick\w*|kill\w*|sla(?:y|in|yed)|fight\w*|fought|"
            r"dodg\w*|parr(?:y|ied|ies)|bit(?:e|es|ing|ten)|claw\w*|blood\w*|wound\w*|bleed\w*|bled",
    "trade": r"buy|buys|bought|buying|sell|sells|sold|selling|trade[sd]?|trading|prices?|priced|pay|pays|paid|paying|"
             r"costs?|worth|bargain\w*|deals?",
    "numbers": r"\d[\d,.]*|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|fifty|"
               r"hundred|thousand|million|dozen",
    "skips": r"\w+\s+(?:hours?|days?|weeks?|months?|years?)\s+later|the\s+(?:next|following)\s+(?:morning|day|night|"
             r"evening|week)|by\s+nightfall"}
LEX = {name: re.compile(rf"\b(?:{pattern})\b", re.I) for name, pattern in LEXICON.items()}
STOPCAP = set("I The A An He She It They We You His Her Their Its This That These Those But And Or So Then When What "
              "Where Why How Who Mr Mrs Ms Dr Sir Lady Lord God Monday Tuesday Wednesday Thursday Friday Saturday Sunday "
              "January February March April May June July August September October November December OK Okay Yes No Oh "
              "Not Just Still Now There Here If As At In On For With From By To Of Maybe Well Hey".split())
# Families decide the headline count, content and surface apart; a measure the operator chose to depart on
# is printed and never counted (DECISIONS chapter-length and code-owned-sheet; LEARNINGS 1.8; third person).
CONTENT = {"furniture": ["sys_lines_k", "displays_k", "sys_share", "max_window"], "progression": ["events_k"],
           "dialogue": ["dialogue", "turns_k"], "cast": ["names", "open_names"], "interior": ["inter_k"],
           "violence": ["viol_k"], "trade": ["trade_k", "money_k", "admin_k"], "other": ["numbers_k", "excl_k", "skips_k"]}
SURFACE = {"length": ["words"], "paragraphing": ["wpp", "paras_k"], "sentences": ["sent_med", "short"]}
CHOSEN = {"furniture": "code-owned status lines", "progression": "early and regular progress", "length": "1,500-word posts"}
NOTES = ["Genre System counts are floors: the RoyalRoad dump flattened tables and lost italics, so ours can look heavier.",
         "No tells placement: the shelf ceilings drifted under the port (Defiance absence 2.8, The Gam3 echo 2.0).",
         "One serial is one brief and one draft line: this describes the serial, not the system."]
# The precision audit (20 located hits a half, experiments/2026-09-28-genre-baseline): under 0.8 on either half.
LOOSE = {"events_k": "genre 10/20", "trade_k": "genre 13/20", "viol_k": "ours 7/20", "inter_k": "ours 11/16, genre 15/20",
         "skips_k": "genre 15/20"}
fmt = lambda v: "-" if v is None else f"{v:.2f}" if isinstance(v, float) and abs(v) < 100 else f"{v:.0f}"  # noqa: E731
LOCATE = {"furniture": lambda s: furniture(s), "progression": lambda s: bool(LVL.search(s) or CAP.search(s) or DELTA.search(s)),
          "trade": lambda s: bool(LEX["trade"].search(s) or checks.MONEY.search(s) or checks.ADMIN.search(s)),
          "violence": lambda s: bool(LEX["viol"].search(s)), "interior": lambda s: bool(LEX["inter"].search(s)),
          "dialogue": lambda s: '"' in s, "other": lambda s: bool(LEX["skips"].search(s) or s.rstrip("\"')]").endswith("!"))}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("\r\n", "\n").translate({0x201C: '"', 0x201D: '"', 0x2018: "'", 0x2019: "'"})
    text = re.sub(r"^[ \t]*(?:[*\-_~=—–][ \t]*){3,}$", "", text, flags=re.M)
    return re.sub(r"(?<![\w*])[*_]{1,2}(?=\S)|(?<=\S)[*_]{1,2}(?![\w*])", "", text)


def furniture(line: str) -> bool:
    return not REJ.match(line) and bool(BR.match(line) or AN.match(line) or TAGGED.match(line) or STAT.match(line))


def measure(raw: str) -> dict:
    """Every census measure of one text. Raw counts ride along for the book window and the port check."""
    lines, runs, run, blanks, position, prose = normalize(raw).split("\n"), [], [], 0, 0, []
    first_sys = first_event = None
    furn_lines = furn_words = events = events_v0 = 0
    values: dict[str, int] = {}
    for line in (s.strip() for s in lines):
        n = len(WORD.findall(line))
        if not line:
            blanks += 1
            if blanks > 1 and run:
                runs, run = runs + [run], []
            continue
        blanks = 0
        if furniture(line):
            furn_lines, furn_words, run = furn_lines + 1, furn_words + n, run + [line]
            first_sys = position if first_sys is None else first_sys
            field = FIELD.match(line) if not line.rstrip("]>").endswith(".") else None  # a closing stop marks a notice
            size = field and int((field[3] or field[2]).replace(",", ""))
            grew = bool(field and size > values.get(field[1].lower(), size))
            if field:
                values[field[1].lower()] = size
            if grew or LVL.search(line) or CAP.search(line) or DELTA.search(line):
                events, first_event = events + 1, position if first_event is None else first_event
        else:
            runs, run = (runs + [run], []) if run else (runs, run)
            prose += [(position, line)] if n else []  # a wordless line is no paragraph
        position += n
    runs += [run] if run else []
    sentences = []
    for at, line in prose:
        for m in SENT.finditer(line):
            if WORD.search(m.group()):
                sentences.append(m.group().strip())
                if LVL.search(m.group()) or CAP.search(m.group()) or DELTA.search(m.group()):
                    events, events_v0 = events + 1, events_v0 + 1
                    first_event = at if first_event is None else first_event
    total, text = max(position, 1), "\n".join(line for _, line in prose)
    pw = max(len(WORD.findall(text)), 1)
    speech = re.findall(r'"[^"\n]*(?:"|$)', text)
    narration = re.sub(r'"[^"\n]*(?:"|$)', " ", text)
    lower = {w for w in WORD.findall(text) if w.islower()}
    def names(passage: str, least: int) -> int:
        seen: dict[str, int] = {}
        for sentence in SENT.findall(passage):
            for token in WORD.findall(sentence)[1:]:
                if token[:1].isupper() and token[1:].islower() and token not in STOPCAP and token.lower() not in lower:
                    seen[token] = seen.get(token, 0) + 1
        return sum(v >= least for v in seen.values())
    lengths = [len(WORD.findall(s)) for s in sentences] or [0]
    paragraphs = [len(WORD.findall(line)) for _, line in prose] or [0]
    k, fields = 1000.0, [sum(bool(FIELD.match(s)) for s in r) for r in runs]
    rate = lambda name, base=None: k * len(LEX[name].findall(base or text)) / (len(WORD.findall(base)) if base else pw)
    return {"words": total, "wpp": statistics.median(paragraphs), "paras_k": k * len(paragraphs) / total,
            "sent_med": statistics.median(lengths), "short": sum(n < 4 for n in lengths) / len(lengths),
            "sys_lines_k": k * furn_lines / total, "displays_k": k * len(runs) / total, "sys_share": furn_words / total,
            "max_window": max([f for f in fields if f >= 3] or [0]), "events_k": k * events / total,
            "dialogue": sum(len(WORD.findall(s)) for s in speech) / pw, "turns_k": k * len(speech) / total,
            "names": names(" ".join(text.split()[:1500]), 2), "open_names": names(" ".join(text.split()[:300]), 1),
            "inter_k": rate("inter", narration), "viol_k": rate("viol"), "trade_k": rate("trade"),
            "money_k": k * len(checks.MONEY.findall(text)) / pw, "admin_k": k * len(checks.ADMIN.findall(text)) / pw,
            "numbers_k": rate("numbers"), "excl_k": k * sum(s.rstrip("\"')]").endswith("!") for s in sentences) / total,
            "skips_k": rate("skips"), "person_k": k * len(checks.FIRST.findall(narration)) / pw,
            "first_system_word": first_sys, "first_event_word": first_event, "events": events,
            "events_v0_k": k * (events_v0 + len(runs)) / total, "system_lines": furn_lines}


def deciles(values: list[float]) -> tuple[float, float, float]:
    v = sorted(values)
    q = statistics.quantiles(v, n=10, method="inclusive") if len(v) > 1 else v * 9
    return q[0], statistics.median(v), q[-1]


def outside(x: float, values: list[float]) -> bool:
    low, _, high = deciles(values)
    return x < low or x > high


def family_count(ours: dict, reference: list[dict], families: dict, counted: bool = True) -> list[str]:
    return [f for f, keys in families.items() if (not counted or f not in CHOSEN)
            and any(outside(ours[m], [r[m] for r in reference]) for m in keys if m not in LOOSE)]


def placement(x: float, values: list[float]) -> dict:
    low, mid, high = deciles(values)
    mad = statistics.median([abs(v - mid) for v in values]) * 1.4826
    return {"p10": low, "p50": mid, "p90": high, "pct": 100 * (sum(v < x for v in values) + 0.5 * sum(v == x for v in values)) / len(values),
            "z": (x - mid) / mad if mad else None, "flag": "below" if x < low else "above" if x > high else ""}


def corpus() -> dict:
    """The genre side, measured once per bench.py and manifest version, cached beside the corpus."""
    key = files.sha(Path(__file__).read_bytes() + MANIFEST.read_bytes())[:16]
    cache = CORPUS / f"measures-{key}.json"
    if cache.is_file():
        return files.load(cache)
    rows = []
    for fiction in files.load(MANIFEST)["fictions"]:
        texts = [files.read(CORPUS / str(fiction["fiction_id"]) / f"ch{c['n']:02d}.txt") for c in fiction["chapters"]]
        rows.append({k: fiction[k] for k in ("fiction_id", "stratum", "litrpg", "era")} | {"chapters": [measure(t) for t in texts]})
    files.save(cache, {"version": VERSION, "rows": rows})
    return files.load(cache)


def window(texts: list[str], budget: int) -> dict:
    """The book read to the same word budget: first display and first gain offsets, gains and names so far."""
    kept, count = [], 0
    for line in "\n".join(texts).split("\n"):
        if count >= budget:
            break
        kept.append(line)
        count += len(WORD.findall(line))
    m = measure("\n".join(kept))
    return {"first_system_word": m["first_system_word"], "first_event_word": m["first_event_word"], "events": m["events"]}


def located(text: str, family: str) -> str:
    """Our chapter.md line numbers carrying a family's count, for a flagged family."""
    test = LOCATE.get(family, lambda s: False)
    hits = [str(i) for i, line in enumerate(normalize(text).split("\n"), 1) if line.strip() and test(line.strip())]
    return ", ".join(hits[:12]) + (f" (+{len(hits) - 12})" if len(hits) > 12 else "")


def ours(slug: str) -> list[dict]:
    out = []
    for here in sorted((files.home() / "serials" / slug).glob("ch[0-9][0-9]")):
        if here.name != "ch00" and (here / "chapter.md").is_file():  # every stored sibling draft gives the band
            drafts = [checks.normalize(files.read(p))[0] for p in sorted(here.glob("calls/draft-d*/final.md"))]
            out.append({"n": int(here.name[2:]), "text": files.read(here / "chapter.md"),
                        "m": measure(files.read(here / "chapter.md")), "drafts": [measure(d) for d in drafts]})
    return out


def rows_for(ch: dict, ref: list[dict], top: list[dict], off: list[dict], last: dict) -> tuple[list[str], dict]:
    k, m, lines, measures, shown = ch["n"], ch["m"], [], {}, set()
    for family, keys in (CONTENT | SURFACE).items():
        for key in keys:
            values, theirs = [r[key] for r in ref], [r[key] for r in off]
            place = placement(m[key], values)
            eras = [[r["chapters"][k - 1][key] for r in top if len(r["chapters"]) >= k and r["era"] == e]
                    for e in ("2021-22", "2024-25")]
            spread = statistics.median([abs(v - place["p50"]) for v in values]) * 1.4826 or None
            gap = abs(statistics.median(eras[0]) - statistics.median(eras[1])) / spread if spread and all(eras) else None
            area = sum((x > y) + 0.5 * (x == y) for x in values for y in theirs) / (len(values) * len(theirs)) if off else None
            band, where = [d[key] for d in ch["drafts"]], place["flag"] and family not in shown
            measures[key] = place | {"ours": m[key], "era_gap_z": gap, "auc": area}
            shown |= {family} if where else set()
            generic = " (not genre-specific)" if area is not None and 0.4 <= area <= 0.6 else ""
            lines.append(f"| {family}{' (chosen)' if family in CHOSEN else ''} | {key}{' (loose)' * (key in LOOSE)} | {fmt(m[key])} | "
                         f"{fmt(min(band)) + '-' + fmt(max(band)) if band else '-'} | {fmt(place['p10'])} / {fmt(place['p50'])}"
                         f" / {fmt(place['p90'])} | {place['pct']:.0f} | {fmt(place['z'])} {place['flag']} | {fmt(gap)} | "
                         f"{fmt(area)}{generic} | {fmt(last.get(key, {}).get('pct'))} | {located(ch['text'], family) if where else ''} |")
    return lines, measures


def baseline(slug: str) -> Path:
    rows, chapters = corpus()["rows"], ours(slug)
    top = [r for r in rows if r["stratum"] == "top" and r["litrpg"]]
    at = lambda group, k: [r["chapters"][k - 1] for r in group if len(r["chapters"]) >= k]
    out = files.home() / "serials" / slug / "baseline"
    previous = sorted(out.glob("*.json"))
    last = files.load(previous[-1]) if previous else {}
    last = {c["n"]: c["measures"] for c in last.get("chapters", [])} if last.get("version") == VERSION else {}
    report = {"version": VERSION, "bench": files.sha(Path(__file__).read_bytes())[:12],
              "manifest": files.sha(MANIFEST.read_bytes())[:12], "commit": files.revision()[:12], "chapters": []}
    lines = [f"# Genre census: {slug} ({VERSION}, {files.utc()})", "",
             f"bench {report['bench']}, manifest {report['manifest']}, commit {report['commit']}. Reference: {len(top)} "
             "LitRPG-tagged RoyalRoad titles with 1,000+ followers (cached 2021-22 and 2024-25 releases), our chapter N "
             "against their chapter N. Measured by code on both halves; a description, never a verdict.", ""]
    lines += [f"- {note}" for note in NOTES] + [f"- Loose measures, printed and never counted (precision under 0.8 on a half): "
                                                f"{', '.join(f'{k} ({v})' for k, v in LOOSE.items())}. Cast is unaudited.", ""]
    for ch in chapters:
        k, ref = ch["n"], at(top, ch["n"])
        null = [len(family_count(r, ref[:i] + ref[i + 1:], CONTENT)) for i, r in enumerate(ref)]
        content, surface = family_count(ch["m"], ref, CONTENT), family_count(ch["m"], ref, SURFACE)
        chosen = [f for f in family_count(ch["m"], ref, CONTENT | SURFACE, counted=False) if f in CHOSEN]
        low, mid, high = deciles(null)
        lines += [f"## Chapter {k}: outside the genre's 10-90% band on {len(content)} of {len(CONTENT) - 2} content "
                  f"families (genre chapter {k}s: median {mid:.0f}, 10-90% {low:.0f}-{high:.0f}); surface {len(surface)} of 3", "",
                  f"Outside: {', '.join(content + surface) or 'none'}. Chosen departures, printed and not counted: "
                  f"{', '.join(f'{f} ({CHOSEN[f]})' for f in chosen) or 'none'}. {len(ref)} genre chapter {k}s.", "",
                  "| family | measure | ours | our drafts | genre p10 / p50 / p90 | pct | z | era gap z | off-genre AUC "
                  "| last pct | our lines |", "|---|---|---|---|---|---|---|---|---|---|---|"]
        table, measures = rows_for(ch, ref, top, at([r for r in rows if r["stratum"] == "off"], k), last.get(k, {}))
        lines += table + [""]
        report["chapters"].append({"n": k, "content_outside": content, "surface_outside": surface,
                                   "null": [low, mid, high], "measures": measures})
    budget = sum(ch["m"]["words"] for ch in chapters)
    mine = window([ch["text"] for ch in chapters], budget)
    theirs = [window([files.read(p) for p in sorted((CORPUS / str(r["fiction_id"])).glob("ch*.txt"))], budget) for r in top]
    lines += [f"## Book window: the first {budget} words (our chapters 1-{len(chapters)})", "",
              "| measure | ours | genre p10 / p50 / p90 | genre with none | pct |", "|---|---|---|---|---|"]
    for key in ("first_system_word", "first_event_word", "events"):
        values = [w[key] for w in theirs if w[key] is not None]
        pct = round(placement(mine[key], values)["pct"]) if mine[key] is not None and values else None
        lines.append(f"| {key} | {fmt(mine[key])} | {' / '.join(fmt(float(v)) for v in deciles(values))} | "
                     f"{sum(w[key] is None for w in theirs)} of {len(theirs)} | {fmt(pct)} |")
    report["window"] = {"words": budget, "ours": mine}
    lines += ["", "## Reference rows, chapter 1 (content families outside the band)", ""]
    for name, paths in (("Lite's chapter 1 (2026-09-27)", [ROOT / "experiments/2026-09-27-opening/lite/chapter.md"]),
                        ("the incumbent's chapter 1s, median", sorted(INCUMBENT.glob("*/chapters/Chapter1.txt")))):
        counts = [len(family_count(measure(files.read(p)), at(top, 1), CONTENT)) for p in paths if p.is_file()]
        lines.append(f"- {name}: {statistics.median(counts):.0f} of {len(CONTENT) - 2} ({len(counts)} texts)"
                     if counts else f"- {name}: not on disk")
    stamp = files.utc()
    files.save(out / f"{stamp}.json", report)
    files.write(out / f"{stamp}.md", "\n".join(lines) + "\n")
    return out / f"{stamp}.md"


if __name__ == "__main__":
    if sys.argv[1:2] != ["baseline"] or len(sys.argv) != 3:
        raise SystemExit(__doc__)
    print(baseline(sys.argv[2]))
