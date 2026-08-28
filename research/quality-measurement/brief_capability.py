"""brief_capability.v0 — can a brief move tone, and can it break the premise lock?

`plan/brief-capability-validity.md` is the registration; this module carries the frozen bytes
and every registered definition. Read that first.

**The question is the operator's**, from the fifth read: *"I didn't say Light Fantasy missing
was a defect, I was just concerned we build a system that is not capable of producing this."*
Every listing this project has drawn ran under an empty brief and all four dossiers are
disaster-shaped, so *won't by default* and *can't when asked* predict the same artifacts on
disk. One axis — the brief — separates them.

**No model judges anything here.** Models write listings; code counts tokens and divides,
against the market's own distribution and against our own empty-brief baseline. The one
lexicon (T) is a membership count over OUR outputs in §116's shape — never a prompt clause,
never a gate.

**`label` is in the design expecting to misbehave.** §136 measured `progression fantasy`
outweighing every rule in the prompt. An arm running only a good brief cannot tell *a brief
works* from *a label works*.

Free legs first; the paid run refuses without `--yes`:

    uv run python research/quality-measurement/brief_capability.py --selftest
    uv run python research/quality-measurement/brief_capability.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from hashlib import sha256
from itertools import combinations
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent / "src"))

import listing_arms  # noqa: E402

DERIVED = HERE / "derived"
RESULTS = HERE / "results"

BRIEF_CAPABILITY_VERSION = "brief_capability.v0"

#: **Byte-frozen.** The only axis. `empty` is the control every listing on disk was drawn
#: under; `label` is the two-word shelf label §136 measured, included so that "a brief works"
#: and "a label works" cannot be confused; `situation` is a constraint about stakes carrying no
#: tonal adjective and no genre word, so that a tonal move under it was moved by the situation.
BRIEFS: dict[str, str] = {
    "empty": "",
    "label": "light fantasy",
    "situation": (
        "Nobody dies in this one. The worst thing that can happen is that somebody loses the "
        "work they are good at, in front of people whose opinion they mind."
    ),
}

#: The cast, in roster order. Held fixed: this arm varies the brief and nothing else.
WRITERS = ("ferreira", "halloran", "vance", "okonjo")

#: Draws per writer per condition — the same K as every sibling instrument (§124).
K_DRAWS = 4

#: Refuse above this many calls without --yes. The exact plan is 48.
CALL_GUARD = 60

#: **Byte-frozen.** T's family. §116's shape: a membership count over our own outputs, with
#: that entry's discipline attached — a recall-tuned list run as a gate has inverted error
#: costs, so T is reported and never gates anything. Narrow it only on a measured false
#: positive, and keep the pre-narrowing number beside the post (§107.9.1, §116.8).
THREAT = re.compile(
    r"\b(kill|kills|killed|killing|die|dies|died|dying|death|dead|corpse|blood|bloody|"
    r"monster|monsters|beast|beasts|survive|survival|kill_count|slaughter|murder|"
    r"fear|afraid|terror|terrified|frighten|frightened|scream|screams|screaming|"
    r"wound|wounds|wounded|scar|scars|pain|agony|torture|"
    r"weapon|weapons|blade|sword|knife|gun|war|battle|violence|violent|"
    r"threat|threats|danger|dangerous|doom|apocalypse|ruin|rot|plague|curse|cursed)\b",
    re.I,
)

#: Stopwords stripped before P's Jaccard, so the statistic reads what a sentence is ABOUT
#: rather than how English glues sentences together.
_STOP_TEXT = (
    "a an the and or but so then of to in on at by for with from as is are was were be been "
    "being it its this that these those he she they them his her their him you your i my me "
    "we our us not no nor if when while into out up down over under again very just only own "
    "same than too can will would could should has have had do does did done there here what "
    "which who whom whose all any both each few more most other some such one"
)
STOP = frozenset(_STOP_TEXT.split())

SENT = re.compile(r"(?<=[.!?])\s+")
WORD = re.compile(r"[a-z0-9']+")


def registration_digest() -> str:
    material = json.dumps(
        {
            "version": BRIEF_CAPABILITY_VERSION,
            "briefs": BRIEFS,
            "writers": list(WRITERS),
            "k_draws": K_DRAWS,
            "threat": THREAT.pattern,
            "stop": sorted(STOP),
            "call_guard": CALL_GUARD,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return sha256(material.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------- deterministic parts


def first_sentence(text: str) -> str:
    """The opening sentence — the unit §4.3 found locked, and the unit P measures."""
    parts = [part for part in SENT.split(" ".join(text.split())) if part.strip()]
    return parts[0] if parts else ""


def opening_tokens(text: str) -> frozenset[str]:
    """P's coordinate: the opening sentence's content tokens, lowercased and de-stopworded."""
    return frozenset(
        token for token in WORD.findall(first_sentence(text).lower()) if token not in STOP
    )


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    return len(a & b) / len(union) if union else 1.0


def premise_lock(texts: list[str]) -> float | None:
    """P: mean pairwise Jaccard over the draws' opening-sentence token sets.

    High means the writer opens the same way every draw. `None` below two draws, because one
    draw has no agreement to report and folding it in as 1.0 would invent a lock.
    """
    sets = [opening_tokens(text) for text in texts]
    if len(sets) < 2:
        return None
    return statistics.fmean(_jaccard(a, b) for a, b in combinations(sets, 2))


def threat_per_100(text: str) -> float:
    """T: threat-family members per hundred words. Reported, never a gate (§116)."""
    words = len(text.split()) or 1
    return 100 * len(THREAT.findall(text)) / words


def coordinator_per_100(text: str) -> float:
    """C: `and`/`then` per hundred words — reader-read-5 §4.1's statistic, carried free."""
    words = len(text.split()) or 1
    return 100 * len(re.findall(r"\b(and|then)\b", text, re.I)) / words


def between_writer_lock(by_writer: dict[str, list[str]]) -> float | None:
    """KP0, the arm's own sham: P computed across DIFFERENT writers inside one condition.

    Different writers writing different premises must agree less than one writer agrees with
    itself. If they do not, P is reading the prompt rather than the premise and the condition
    says nothing about premise lock.
    """
    pairs: list[float] = []
    names = sorted(by_writer)
    for left, right in combinations(names, 2):
        for a in by_writer[left]:
            for b in by_writer[right]:
                pairs.append(_jaccard(opening_tokens(a), opening_tokens(b)))
    return statistics.fmean(pairs) if pairs else None


def _mean(rows: list[dict[str, Any]], key: str) -> float | None:
    """A leg's mean of one counter, or None when the leg drew nothing — never a zero."""
    return statistics.fmean([row[key] for row in rows]) if rows else None


def summarise(
    drawn: list[dict[str, Any]], band: dict[str, tuple[float, float, float]]
) -> dict[str, Any]:
    """Every registered readout, per condition. No bar is applied anywhere."""
    out: dict[str, Any] = {}
    for condition in BRIEFS:
        rows = [row for row in drawn if row["condition"] == condition]
        by_writer: dict[str, list[str]] = {}
        for row in rows:
            by_writer.setdefault(row["writer"], []).append(row["listing"])
        within = {who: premise_lock(texts) for who, texts in sorted(by_writer.items())}
        measured = [value for value in within.values() if value is not None]
        degenerate = sorted(who for who, texts in by_writer.items() if len(set(texts)) < len(texts))
        out[condition] = {
            "draws": len(rows),
            "P_within_writer": within,
            "P_within_mean": statistics.fmean(measured) if measured else None,
            "KP0_between_writer": between_writer_lock(by_writer),
            "KD_degenerate_writers": degenerate,
            "T_per_100": _mean(rows, "threat_per_100"),
            "C_per_100": _mean(rows, "coord_per_100"),
            "words_mean": _mean(rows, "words"),
            "outside_band": sorted({item for row in rows for item in row["outside"]}),
        }
    return out


def plan_calls() -> int:
    """The exact call count. One axis, no worst case: writers x conditions x K."""
    return len(WRITERS) * len(BRIEFS) * K_DRAWS


# -------------------------------------------------------------------------------- selftest


def selftest() -> int:
    failures: list[str] = []

    if plan_calls() != 48:
        failures.append("the registered plan is 4 writers x 3 conditions x K=4 = 48 calls")
    if BRIEFS["empty"] != "":
        failures.append("the control condition must be the empty brief")
    if BRIEFS["label"] != "light fantasy":
        failures.append("the label condition is the two-word shelf label §136 measured")

    if first_sentence("One thing. Two thing. Three.") != "One thing.":
        failures.append("the opening sentence is the first sentence and nothing else")
    if first_sentence("   ") != "":
        failures.append("an empty text has no opening sentence")

    if "the" in opening_tokens("The screen and the door.") or "screen" not in opening_tokens(
        "The screen and the door."
    ):
        failures.append("P's coordinate is content tokens with stopwords removed")

    same = ["Every screen on Earth lit at once.", "Every screen on Earth lit at once."]
    if premise_lock(same) != 1.0:
        failures.append("two identical openings must lock at 1.0")
    apart = ["Every screen on Earth lit at once.", "A bell rang in the orchard."]
    if premise_lock(apart) != 0.0:
        failures.append("two openings sharing no content token must lock at 0.0")
    if premise_lock(["only one draw."]) is not None:
        failures.append("one draw has no agreement and must not report a lock")

    # KP0 must separate: one writer repeating itself against two writers who do not.
    locked = {"a": ["Every screen on Earth lit."] * 2, "b": ["A bell rang in the orchard."] * 2}
    within = statistics.fmean([premise_lock(v) or 0 for v in locked.values()])
    if not (between_writer_lock(locked) or 0) < within:
        failures.append("KP0 must sit below within-writer agreement or P reads the prompt")

    if threat_per_100("he killed the monster") != 50.0:
        failures.append("T is family members per hundred words of the listing's own count")
    if threat_per_100("a quiet afternoon in the orchard") != 0.0:
        failures.append("a listing with no family member scores zero, not a floor")
    if abs(coordinator_per_100("one and two then three") - 40.0) > 1e-9:
        failures.append("C counts and/then per hundred words")

    if registration_digest() != registration_digest():
        failures.append("registration digest unstable")

    for line in failures:
        print(f"FAIL {line}", file=sys.stderr)
    print("selftest: " + ("FAILED" if failures else "passed"), file=sys.stderr)
    return 1 if failures else 0


# ------------------------------------------------------------------------------------ the run


def run(registry: Any, band: dict[str, tuple[float, float, float]]) -> tuple[
    list[dict[str, Any]], dict[str, dict[str, int]]
]:
    """One draw per writer per condition per K. Transport failures counted, never scored."""
    from litharness.application import overview as overview_mod
    from litharness.domain import writers as writers_mod

    transport: dict[str, dict[str, int]] = {name: {} for name in BRIEFS}
    drawn: list[dict[str, Any]] = []
    for condition, brief in BRIEFS.items():
        for who in WRITERS:
            writer = writers_mod.CAST[who]
            request = overview_mod.render_overview_request(brief, writer)
            for draw in range(K_DRAWS):
                try:
                    result, _ = registry.complete(request)
                except Exception as error:  # an outage is a fact about the day, not the brief
                    transport[condition][who] = transport[condition].get(who, 0) + 1
                    print(f"  {condition}/{who}/{draw}: {str(error)[:120]}", file=sys.stderr)
                    continue
                listing = result.text.strip()
                got = listing_arms.panel(listing)
                drawn.append(
                    {
                        "condition": condition,
                        "writer": who,
                        "draw": draw,
                        "listing": listing,
                        "digest": sha256(listing.encode()).hexdigest()[:12],
                        "opening": first_sentence(listing),
                        "threat_per_100": threat_per_100(listing),
                        "coord_per_100": coordinator_per_100(listing),
                        **got,
                        "outside": listing_arms.outside(got, band),
                    }
                )
                print(
                    f"  {condition:9} {who:9} draw{draw} {got['words']:4}w"
                    f"  T {drawn[-1]['threat_per_100']:5.2f}  C {drawn[-1]['coord_per_100']:5.2f}"
                )
    return drawn, transport


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--rivals", default=str(DERIVED / "rivals.json"))
    parser.add_argument("--out", type=Path, default=DERIVED / "brief-capability-text.json")
    parser.add_argument("--report", type=Path, default=RESULTS / "brief-capability.json")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.dry_run and not args.run:
        parser.error("pass one of --selftest, --dry-run, --run")

    calls = plan_calls()
    if args.dry_run:
        print(f"conditions: {', '.join(BRIEFS)}")
        print(f"writers: {', '.join(WRITERS)}")
        print(
            f"calls: {calls} exactly = {len(WRITERS)} writer(s) x {len(BRIEFS)} condition(s) "
            f"x K={K_DRAWS}"
        )
        print(f"registration digest: {registration_digest()}")
        print("dry run: no registry constructed, nothing spent", file=sys.stderr)
        return 0

    if calls > CALL_GUARD and not args.yes:
        print(f"{calls} calls exceeds the {CALL_GUARD} guard; pass --yes", file=sys.stderr)
        return 1
    if not args.yes:
        print("refusing: --run needs --yes; this spend is gated on the operator", file=sys.stderr)
        return 1

    from litharness.providers import build_default_registry  # lazy: heavy, paid path only

    band = listing_arms.market_band(json.loads(Path(args.rivals).read_text(encoding="utf-8")))
    drawn, transport = run(build_default_registry(), band)
    summary = summarise(drawn, band)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(drawn, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {
        "study": BRIEF_CAPABILITY_VERSION,
        "registration": "plan/brief-capability-validity.md",
        "registration_digest": registration_digest(),
        # KT: read these before any reading. §145 is the entry on why.
        "transport_failures": transport,
        "calls_planned": calls,
        "market_band": {key: list(value) for key, value in band.items()},
        "conditions": summary,
        "rows": [{key: value for key, value in row.items() if key != "listing"} for row in drawn],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")

    print()
    for condition, block in summary.items():
        print(
            f"{condition:9} P {block['P_within_mean']}  KP0 {block['KP0_between_writer']}  "
            f"T {block['T_per_100']}  C {block['C_per_100']}"
        )
    failed = sum(sum(cell.values()) for cell in transport.values())
    print(f"transport failures: {failed} — read before any verdict")
    print(f"-> {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
