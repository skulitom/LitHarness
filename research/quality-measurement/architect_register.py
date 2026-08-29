"""Does the institutional lean in our worlds sit in our own instruction text, the way §116's did?

**The question, and why it is worth asking twice.** Stage-0 §116 found thirty forged worlds in a
row reaching for debt and ledgers, and the cause was four lines of our own `_RULES`. Read 7 §4.2
names the same shape at a new address — *"bringing up licences, legal licences etc falls under
boring mundane minutia"* — and routes it to a §116-shape audit before any clause is written. Two
simulated-reader pools flagged the register before the operator did, which is the rare case of the
instrument side naming a complaint first and is worth one line in a future validity argument.

**The answer this module measures is the opposite of §116's, and the control is what carries it.**
Between §116 and now, the instruction text was not merely amended but *replaced*: `_RULES` was
de-biased on 2026-08-23 and the whole Forge was retired on 2026-08-26 in favour of a tool-holding
Architect whose task text carries no institutional noun at all. Three regimes therefore exist on
disk over nine worlds, and the rate does not move across them. A lean that survives the deletion
of the text accused of causing it is not caused by that text.

**What the counting rules are, and both are §116's own.**

- *Schema-supplied values are counted separately and never in the rate.* `world vocabulary` prints
  `institution` and `agency` among nine entity roles, and `law`, `economy`, `politics`, `crime`
  among eight consequence domains; a world reaching for those reached for a menu we printed. This
  is §116's rule that `price`, `cost`, `pay` and `bond` were excluded because *"the schema asks
  every world for those and counting them would count this module's own instructions"*.
- *Every word in the family means only the one thing.* §116.8 took `court` out after it bought one
  world in thirty and cost every courtyard, and recorded that this module had narrowed a word
  guard from a measured false positive three times. `PROBE` holds the ambiguous candidates; they
  are reported and never summed into the headline.

**Nothing here is a gate and nothing here declares a bar.** §116 could gate on a premise because
the Forge produced a premise for a person to pick among; the Architect produces no such artifact,
and there is nothing for a membership test to refuse. The rate is a distribution over nine worlds.

**The one confound that decides the reading, and it is not in this file.** The Architect's user
prompt *is the listing*, so a listing that already names an institution hands one to the world
before the Architect writes a record. `listing_words` measures that, and the pilots' listings are
where the reading actually lands.

    uv run python research/quality-measurement/architect_register.py

`uv run`, not the MirrorBench interpreter: this reads book databases and no parquet (CLAUDE.md).
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import statistics
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
DATABASES = ROOT / "runs" / "pilots" / "databases"
PILOTS = ROOT / "runs" / "pilots"

#: Values the schema itself prints. Counting these counts our own menu (§116's exclusion rule).
SCHEMA_SUPPLIED: frozenset[str] = frozenset({
    "institution", "agency", "law", "economy", "politics", "crime", "cast", "creature",
    "place", "carrier", "system", "protagonist", "capability", "religion", "daily_life",
    "craft", "war", "criterion", "constraint", "cardinality_constraint", "change", "view",
    "ordinal", "numeric", "threshold", "equality", "set_inclusion", "pareto",
    "replacement_equivalence",
})

#: Predicates whose `--value` is prose the Architect wrote. A lean would show here or nowhere.
FREE_TEXT_PREDICATES: frozenset[str] = frozenset({
    "world_rule", "consequence", "manifests_as", "edge", "price", "claim.content", "asks",
    "costs", "wants",
})

#: The institutional-permission family. Every word means only the one thing, which is the test
#: §116.8 earned by measuring what `court` cost. This is a different family from §116's
#: debt-and-ledger one: the operator's complaint here is charters, licences and bailiffs.
CORE: frozenset[str] = frozenset({
    "licence", "licences", "license", "licenses", "licensed", "licensing", "unlicensed",
    "charter", "charters", "chartered", "guild", "guilds", "tribunal", "tribunals",
    "bailiff", "bailiffs", "writ", "writs", "docket", "dockets", "magistrate", "magistrates",
    "clerk", "clerks", "assize", "assizes", "warrant", "warrants", "ordinance", "ordinances",
    "statute", "statutes", "bylaw", "bylaws", "decree", "decrees", "registry", "registries",
    "registrar", "notary", "reeve", "reeves", "constable", "constables", "tariff", "tariffs",
    "levy", "levies", "permit", "permits", "permitted", "certificate", "certificates",
    "certification", "accreditation", "credential", "credentials", "inspector", "inspectors",
    "inspection", "inspections", "ledger", "ledgers", "deed", "deeds", "petition", "petitions",
    "affidavit", "jurisdiction", "exemption", "exemptions", "dispensation", "quota", "quotas",
    "revoke", "revoked", "revocation", "bureau", "ministry",
})

#: Ambiguous in ordinary English. Reported beside the rate and never inside it. `court` is
#: absent on purpose: §116.8 removed it after a measured false positive on an arena.
PROBE: frozenset[str] = frozenset({
    "register", "registers", "registered", "office", "offices", "file", "filed", "filing",
    "clearance", "notice", "notices", "council", "councils", "seal", "sealed", "stamp",
    "stamped", "toll", "tolls", "appeal", "appeals", "board", "sanction", "sanctioned",
    "archive", "archives", "intake", "expires", "expired", "dues",
})

#: Which instruction text each world was built under. The regimes are the control: `_RULES` was
#: de-biased by §116 on 2026-08-23 and the whole Forge was retired on 2026-08-26.
REGIMES: dict[str, str] = {
    "serial3": "forge-pre-116", "serial4": "forge-pre-116",
    "serial7": "forge-post-116", "serial8": "forge-post-116", "serial9": "forge-post-116",
    "serial12": "architect", "serial12b": "architect",
    "serial13": "architect", "serial13b": "architect",
}

_WORD = re.compile(r"[a-z]+")


def words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def free_text(path: Path) -> list[tuple[str, str, str]]:
    """(subject, predicate, value) for every record whose value is prose the Architect wrote."""
    rows: list[tuple[str, str, str]] = []
    with sqlite3.connect(path) as conn:
        for subject, predicate, value_json in conn.execute(
            "select subject, predicate, value_json from state_records"
        ):
            if predicate not in FREE_TEXT_PREDICATES or value_json is None:
                continue
            try:
                value = json.loads(value_json)
            except (json.JSONDecodeError, TypeError):
                value = value_json
            if isinstance(value, str) and value not in SCHEMA_SUPPLIED:
                rows.append((subject, predicate, value))
    return rows


def schema_menu_uses(path: Path) -> int:
    """How often a world reached for the institutional items on the schema's own menu."""
    total = 0
    with sqlite3.connect(path) as conn:
        for predicate, value_json, record_json in conn.execute(
            "select predicate, value_json, record_json from state_records"
        ):
            try:
                value = json.loads(value_json) if value_json else None
            except (json.JSONDecodeError, TypeError):
                value = value_json
            role_menu = predicate == "entity_role" and value in {"institution", "agency"}
            domain_menu = (
                predicate == "consequence"
                and bool(record_json)
                and any(
                    f'"{domain}"' in record_json
                    for domain in ("law", "economy", "politics", "crime")
                )
            )
            if role_menu or domain_menu:
                total += 1
    return total


def measure(path: Path) -> dict[str, Any]:
    """One world's institutional free-text rate, with every hit kept for hand-check."""
    rows = free_text(path)
    tokens: list[str] = []
    core: list[dict[str, str]] = []
    probe: list[str] = []
    for _subject, predicate, value in rows:
        found = words(value)
        tokens += found
        for word in found:
            if word in CORE:
                core.append({"word": word, "predicate": predicate, "value": value[:160]})
            elif word in PROBE:
                probe.append(word)
    n = max(1, len(tokens))
    return {
        "world": path.stem,
        "regime": REGIMES.get(path.stem, "unknown"),
        "free_text_values": len(rows),
        "free_text_tokens": len(tokens),
        "core_hits": len(core),
        "core_per_1k": round(1000.0 * len(core) / n, 4),
        "probe_hits": len(probe),
        "schema_menu_uses": schema_menu_uses(path),
        "hits": core,
    }


def listing_words(pilot: str) -> dict[str, Any]:
    """The institutional words already in a pilot's listing, before the Architect reads it.

    This is the confound that decides the whole audit: the Architect's user prompt is the
    listing, so a listing naming a charter hands the world one for free.
    """
    path = PILOTS / pilot / "listing.txt"
    if not path.exists():
        return {"pilot": pilot, "listing": None}
    text = path.read_text(encoding="utf-8", errors="replace")
    found = [w for w in words(text) if w in CORE]
    return {"pilot": pilot, "core_words": sorted(set(found)), "core_hits": len(found)}


def _median(values: Iterable[float]) -> float:
    ordered = sorted(values)
    return round(statistics.median(ordered), 4) if ordered else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit the full record with hits")
    args = parser.parse_args()

    worlds = [measure(DATABASES / f"{name}.db") for name in sorted(REGIMES)
              if (DATABASES / f"{name}.db").exists()]
    by_regime: dict[str, list[float]] = {}
    for world in worlds:
        by_regime.setdefault(world["regime"], []).append(world["core_per_1k"])

    payload = {
        "instrument": "architect_register.v0",
        "worlds": worlds,
        "by_regime": {
            regime: {
                "n": len(rates),
                "median_core_per_1k": _median(rates),
                "min": round(min(rates), 4),
                "max": round(max(rates), 4),
            }
            for regime, rates in sorted(by_regime.items())
        },
        "listings": [listing_words(p) for p in ("pilot12", "pilot13")],
        "no_bar": (
            "a distribution over nine worlds. Nothing here is a gate and no threshold is "
            "declared; the Architect produces no premise for a membership test to refuse"
        ),
    }
    if args.json:
        print(json.dumps(payload, indent=2))
        return 0

    print(f"{'world':12s} {'regime':16s} {'tokens':>7s} {'core':>5s} {'/1k':>7s} "
          f"{'probe':>6s} {'menu':>5s}")
    for world in worlds:
        print(f"{world['world']:12s} {world['regime']:16s} {world['free_text_tokens']:7d} "
              f"{world['core_hits']:5d} {world['core_per_1k']:7.2f} {world['probe_hits']:6d} "
              f"{world['schema_menu_uses']:5d}")
    print("\nby regime (median core per 1,000 free-text words):")
    for regime, stats in payload["by_regime"].items():
        print(f"  {regime:16s} n={stats['n']}  median={stats['median_core_per_1k']:6.2f}  "
              f"range={stats['min']:.2f}-{stats['max']:.2f}")
    print("\nthe listing the Architect was handed, before it declared anything:")
    for listing in payload["listings"]:
        print(f"  {listing['pilot']:8s} {listing.get('core_hits', 0)} hits "
              f"{listing.get('core_words', [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
