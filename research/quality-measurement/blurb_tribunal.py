"""blurb_tribunal.v0 — one agent flags, another defends, and code decides.

`plan/blurb-tribunal-validity.md` is the registration; this module carries the frozen bytes
and every registered definition. Read that first.

**The idea.** A model asked whether phrasing is idiomatic is the wrong instrument (boundary
5); a model asked to *detect against visible references* found the first non-inverted
separation (`blurb_shelf`). The tribunal pushes one step further: the flagger quotes spans it
would not expect from this market's writers, and the advocate — who sees only the phrase,
never the target listing, never that anything was flagged — must produce a parallel from the
reference listings it was shown. The third seat is **code**: a claimed parallel either occurs
verbatim in the named reference listing or it does not. Disagreement is resolved by checkable
evidence rather than a third opinion, which is what keeps the resolver out of the dead verdict
channel — a model resolving two models' dispute is a judge, and a string-membership check is
not.

**Stage 2 is bounded.** Each draw may return at most `FLAG_MAX_ITEMS` flags; unique located
flags are deduplicated across draws and truncated to `FLAG_MAX_ITEMS` per target (strongest
draw support first, ties by text) before advocacy, so stage 2 costs at most `FLAG_MAX_ITEMS`
calls per target and the dry-run arithmetic is exact rather than estimated.

**Transport rule, inherited from blurb_rewrite:** a failed call is excluded from every rate
and counted in `transport_failures`, never scored. A failed flag draw produces no flags; a
failed defend call offers no evidence, so its flag survives by default and stays out of the
advocacy-integrity denominator. Read the failure counts before any verdict.

**Prose firewall.** Every flag and every parallel enters a result row only through
`blurb_shelf.phrase_record`: verbatim text only when the span lives in one of OUR listings;
token offsets plus `located` for any market listing, references included. Results carry no
third-party prose; full raw text goes only to the gitignored `derived/` sidecar.

Free legs first; the paid run refuses without both `--yes` and the undocumented
`--i-am-the-gated-run`:

    uv run python research/quality-measurement/blurb_tribunal.py --selftest
    uv run python research/quality-measurement/blurb_tribunal.py --dry-run \
        --pool derived/rivals.json derived/rivals-low.json \
        --texts runs/pilots/pilot7/listing.json
"""

from __future__ import annotations

import argparse
import inspect
import json
import random
import statistics
import sys
from hashlib import sha256
from itertools import combinations
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent / "src"))

import blurb_shelf  # noqa: E402
import listing_arena  # noqa: E402

# KG's statistic is blurb_rewrite's registered seeded pair bootstrap — imported, never
# reinvented. Its module import pulls the provider stack, so it is imported defensively and
# mirrored byte-for-byte if unavailable; PRE_REGISTRATION records which one ran.
try:
    from blurb_rewrite import BOOTSTRAP_DRAWS, BOOTSTRAP_SEED, gradient_stat
except Exception:  # pragma: no cover — the mirror below is the documented fallback
    BOOTSTRAP_DRAWS = 2_000
    BOOTSTRAP_SEED = 20260826
    gradient_stat = None

RESULTS = HERE / "results"
DERIVED = HERE / "derived"


# ---------------------------------------------------------------- the registration, frozen

BLURB_TRIBUNAL_VERSION = "blurb_tribunal.v0"

#: Draws of the flagger per target; §124's lesson, the same K as both sibling instruments.
K_DRAWS = 4

#: Reference listings shown to both seats, numbered 1-5 in the prompt.
N_REFERENCES = 5

#: Schema cap on flags per draw, and the per-target cap on unique flags defended — the bound
#: that makes stage 2's cost exact (see the docstring).
FLAG_MAX_ITEMS = 8

#: Requests carry the measurement conventions: a named profile, the generation class.
PROFILE = "reader.tribunal.v0"
MAX_OUTPUT_TOKENS = 400

#: Refuse above this many worst-case calls without --yes.
CALL_GUARD = 500

#: Leg sizes. Shams are per-target floors, never pooled; every gradient pair contributes both
#: sides (its HIGH partner joins the sham targets when it is not one already).
DEFAULT_SHAMS = 6
DEFAULT_PAIRS = 8

#: KD's floor, the same discipline as blurb_shelf's: below this mean cross-draw agreement the
#: flagger disagrees with itself more than it agrees, and no direction is readable.
KD_AGREEMENT_FLOOR = 0.5

#: Reuse by import — the same one-sentence persona the shelf instrument uses, deliberately:
#: both seats read as the same years-on-this-market reader, and nothing in either seat judges.
SYSTEM = blurb_shelf.SYSTEM

#: **Byte-frozen.** Stage 1. Detection phrasing, "quote exactly", and an explicit empty-list
#: permission (the shelf run's lesson: an ask that under-invites "none" dirties its floor).
ASK_FLAG = (
    "Quote every phrase in the listing under reading that would not appear in a listing "
    "written by this market's writers. Quote exactly. An empty list is a normal answer."
)

#: **Byte-frozen.** Stage 2. The phrase alone — never the target listing, never a hint that
#: the phrase was flagged or why. Zero means "no parallel exists".
ASK_DEFEND = (
    "Here is a phrase: {phrase}. If a construction that works the same way appears in any "
    "of these five listings, quote it exactly and name its listing number. If none does, "
    "answer 0."
)

#: **Byte-frozen.** One field, closed: the quoted phrases. Nothing rates, ranks or explains.
FLAG_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["flags"],
    "additionalProperties": False,
    "properties": {
        "flags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Exact phrases from the listing under reading. Empty list if none.",
            "maxItems": FLAG_MAX_ITEMS,
        },
    },
}

#: **Byte-frozen.** Two fields, closed: the parallel and its listing. `from_listing` 0 pairs
#: with an empty `parallel`; any other number demands a non-empty quote.
DEFEND_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["parallel", "from_listing"],
    "additionalProperties": False,
    "properties": {
        "parallel": {
            "type": "string",
            "description": (
                "Quote the exact parallel from the named listing. Empty string if you "
                "answered 0."
            ),
        },
        "from_listing": {"type": "integer", "minimum": 0, "maximum": N_REFERENCES},
    },
}


PRE_REGISTRATION: dict[str, Any] = {
    "version": BLURB_TRIBUNAL_VERSION,
    "system": SYSTEM,
    "ask_flag": ASK_FLAG,
    "ask_defend": ASK_DEFEND,
    "flag_schema": FLAG_SCHEMA,
    "defend_schema": DEFEND_SCHEMA,
    "k_draws": K_DRAWS,
    "n_references": N_REFERENCES,
    "flag_max_items": FLAG_MAX_ITEMS,
    "max_output_tokens": MAX_OUTPUT_TOKENS,
    "profile": PROFILE,
    "call_guard": CALL_GUARD,
    "default_shams": DEFAULT_SHAMS,
    "default_pairs": DEFAULT_PAIRS,
    "kd_agreement_floor": KD_AGREEMENT_FLOOR,
    "stage_two_cap": (
        "unique located flags per target are truncated to FLAG_MAX_ITEMS, strongest draw "
        "support first, ties broken by normalised text — stage 2 is bounded by "
        "FLAG_MAX_ITEMS x targets"
    ),
    "survival": (
        "a flag survives iff no defense's parallel locates verbatim in the named reference "
        "listing (blurb_shelf.locate_tokens)"
    ),
    "kg_statistic": (
        "blurb_rewrite.gradient_stat (imported)"
        if gradient_stat is not None
        else "mirror of blurb_rewrite.gradient_stat (import unavailable)"
    ),
    "bootstrap_draws": BOOTSTRAP_DRAWS,
}


def registration_digest() -> str:
    material = json.dumps(PRE_REGISTRATION, sort_keys=True, ensure_ascii=False)
    return sha256(material.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------- deterministic parts


def identity(row: dict[str, Any]) -> str:
    """A pool row's stable id: its source when it carries one, else the page digest."""
    return str(row.get("source") or "") or blurb_shelf.digest_of(blurb_shelf.page(row))


def reference_shelf(high: list[dict[str, Any]], target: dict[str, Any]) -> list[dict[str, Any]]:
    """The five HIGH listings nearest the target's word count, the target excluded by identity.

    A HIGH target must never be asked to find parallels against a shelf containing itself —
    the exclusion is by identity, never by position.
    """
    want = len(str(target["listing"]).split())
    others = [row for row in high if identity(row) != identity(target)]
    return blurb_shelf.nearest_high(others, want, N_REFERENCES)


def render_references(references: list[dict[str, Any]]) -> str:
    """The five listings, numbered 1-5, `blurb_shelf.page` shapes separated by blank equals."""
    return "\n\n===\n\n".join(
        f"{number}. {blurb_shelf.page(row)}" for number, row in enumerate(references, 1)
    )


def render_flag_prompt(references: list[dict[str, Any]], target: dict[str, Any]) -> str:
    """References first, then the listing under reading, then the frozen ask."""
    return (
        f"{render_references(references)}\n\n===\n\nTHE LISTING UNDER READING:\n\n"
        f"{blurb_shelf.page(target)}\n\n{ASK_FLAG}"
    )


def render_defend_prompt(references: list[dict[str, Any]], phrase: str) -> str:
    """The SAME references, then the phrase alone. No target, no hint that anything was flagged."""
    return f"{render_references(references)}\n\n===\n\n{ASK_DEFEND.format(phrase=phrase)}"


def build_targets(
    high: list[dict[str, Any]],
    low: list[dict[str, Any]],
    n_shams: int,
    n_pairs: int,
    texts: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Every target the battery measures, deterministically, with both sides of each pair.

    Sham targets come off the top of the admitted pool by followers. Each gradient pair's LOW
    side is a gradient-leg target; its HIGH partner is measured too — already a sham target
    when word counts allow, otherwise appended as an additional sham-leg target, so every
    pair has both sides under one registration.
    """
    targets: list[dict[str, Any]] = []
    by_identity: dict[str, dict[str, Any]] = {}

    def add(row: dict[str, Any], leg: str, name: str, pair: int | None = None) -> None:
        target = {"leg": leg, "name": name, "row": row, "pair": pair}
        targets.append(target)
        by_identity[identity(row)] = target

    ranked = blurb_shelf.ranked_by_followers(high)
    for index, row in enumerate(ranked[:n_shams]):
        add(row, "sham", f"sham_{index}:{identity(row)}")
    for index, (partner, bottom) in enumerate(blurb_shelf.matched_pairs(high, low, n_pairs)):
        add(bottom, "gradient", f"gradient_{index}:{identity(bottom)}", pair=index)
        existing = by_identity.get(identity(partner))
        if existing is None:
            add(partner, "sham", f"sham_partner_{index}:{identity(partner)}", pair=index)
        elif existing["pair"] is None:
            # The partner is already a plain sham target — which is the COMMON case, since
            # both the sham roster and `matched_pairs`' partners come off the top of the pool
            # by followers. It must still carry its pair index or KG's (pair, "sham") lookup
            # never finds it and the pair silently drops from the statistic — the gate caught
            # KG running on 2 of 8 pairs while looking like it covered all of them.
            existing["pair"] = index
    for entry in texts:
        add(entry, "ours", f"ours:{entry['name']}")
    return targets


# ------------------------------------------------------------------------------- the scorers


def parse_flags(text: str) -> list[str] | None:
    """`{"flags": [str, ...]}` exactly, else None — one shape, no partial credit.

    Non-JSON, wrong keys, extra keys, a non-list, more than `FLAG_MAX_ITEMS` items, or any
    non-string item are all the same None; folding a malformed answer into the tally would
    score the format, not the flagging.
    """
    if not text:
        return None
    try:
        payload = json.loads(text)
    except ValueError:
        return None
    if not isinstance(payload, dict) or set(payload) != {"flags"}:
        return None
    flags = payload["flags"]
    if not isinstance(flags, list) or len(flags) > FLAG_MAX_ITEMS:
        return None
    if not all(isinstance(flag, str) for flag in flags):
        return None
    cleaned = [" ".join(flag.split()) for flag in flags]
    return [flag for flag in cleaned if flag]


def parse_defense(text: str) -> dict[str, Any] | None:
    """`{"parallel": str, "from_listing": 0-5}` exactly, else None — one shape, no credit.

    Both malformed pairings die here: a named listing with an empty quote, and a 0 with a
    quote beside it, exactly as `blurb_shelf.parse_answer` refuses its mismatched pair.
    """
    if not text:
        return None
    try:
        payload = json.loads(text)
    except ValueError:
        return None
    if not isinstance(payload, dict) or set(payload) != {"parallel", "from_listing"}:
        return None
    number = payload["from_listing"]
    parallel = payload["parallel"]
    if isinstance(number, bool) or not isinstance(number, int) or not 0 <= number <= N_REFERENCES:
        return None
    if not isinstance(parallel, str):
        return None
    if bool(number) != bool(parallel.strip()):  # 0 pairs with empty; a number demands its quote
        return None
    return {"parallel": parallel.strip(), "from_listing": number}


def collect_flags(draw_flags: list[list[str]], listing: str) -> dict[str, Any]:
    """Locate every returned flag in the target listing, deduplicate across draws.

    A returned flag that does not LOCATE is a fabricated quotation, not a flag: it is dropped
    and counted in `unlocated_flags`. Surviving flags are deduplicated by normalised text and
    each carries its draw support — how many of the draws produced it.
    """
    support: dict[str, dict[str, Any]] = {}
    unlocated = 0
    for draw in draw_flags:
        seen_this_draw: set[str] = set()
        for flag in draw:
            span = blurb_shelf.locate_tokens(flag, listing)
            if span is None:
                unlocated += 1
                continue
            key = " ".join(flag.split()).casefold()
            if key not in support:
                support[key] = {"phrase": " ".join(flag.split()), "key": key, "support": 0}
            if key not in seen_this_draw:
                support[key]["support"] += 1
                seen_this_draw.add(key)
    return {
        "flags": sorted(support.values(), key=lambda row: (-row["support"], row["key"])),
        "unlocated": unlocated,
    }


def draw_token_sets(draw_flags: list[list[str]], listing: str) -> list[frozenset[str]]:
    """Per-draw sets of tokens from that draw's LOCATED flags — KD's inputs."""
    sets: list[frozenset[str]] = []
    for draw in draw_flags:
        tokens: set[str] = set()
        for flag in draw:
            span = blurb_shelf.locate_tokens(flag, listing)
            if span is not None:
                tokens.update(token.casefold() for token in flag.split())
        sets.append(frozenset(tokens))
    return sets


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left and not right:
        return 1.0  # two draws that both flagged nothing agree trivially
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def flag_agreement(draw_sets: list[frozenset[str]]) -> float | None:
    """KD: mean pairwise Jaccard of the draws' flagged-token sets.

    The token-set idea of `blurb_rewrite.draw_agreement`, pointed at flags instead of changed
    spans — that module scores rewrite diffs, so its function cannot be called directly, and
    duplicating its bug surface would be worse than mirroring its few lines.
    """
    if len(draw_sets) < 2:
        return None
    return statistics.fmean(_jaccard(a, b) for a, b in combinations(draw_sets, 2))


# -------------------------------------------------------------- the third seat: code


def defense_outcome(defense: dict[str, Any] | None, references: list[dict[str, Any]]) -> str:
    """The deterministic verdict on one defense: "none", "valid", or "fabricated".

    VALID iff the claimed parallel locates verbatim (`locate_tokens`) inside the NAMED
    reference listing. A non-zero `from_listing` whose parallel does not locate is a
    fabricated defense. No model is consulted; membership in a string is not a judgment.
    """
    if defense is None:
        return "none"
    number = defense["from_listing"]
    if number == 0:
        return "none"
    named = references[number - 1]
    span = blurb_shelf.locate_tokens(defense["parallel"], blurb_shelf.page(named))
    return "valid" if span is not None else "fabricated"


def tribunal(
    listing: str,
    draw_flags: list[list[str]],
    defenses: dict[str, dict[str, Any] | None],
    references: list[dict[str, Any]],
    *,
    is_ours: bool,
) -> dict[str, Any]:
    """ONE target's whole mechanism: locate, dedupe, cap, adjudicate, summarise.

    `defenses` maps a flag's dedupe key to its parsed defend answer, or to None when the call
    failed transport or returned a malformed shape — no usable evidence, so the flag survives
    by default and the entry sits outside KA's denominator. There is no function anywhere in
    this module that accepts two targets' rows: floors are per target, never pooled.
    """
    words = len(listing.split()) or 1
    collected = collect_flags(draw_flags, listing)
    capped = collected["flags"][:FLAG_MAX_ITEMS]
    rows: list[dict[str, Any]] = []
    answered = valid = fabricated = surviving = 0
    for flag in capped:
        defense = defenses.get(flag["key"])
        outcome = defense_outcome(defense, references)
        row: dict[str, Any] = {
            "flag": blurb_shelf.phrase_record(flag["phrase"], listing, is_ours=is_ours),
            "support": flag["support"],
            "outcome": outcome,
        }
        if defense is not None:
            answered += 1
            if outcome == "valid":
                valid += 1
            elif outcome == "fabricated":
                fabricated += 1
            named = references[defense["from_listing"] - 1]
            # The parallel names a MARKET listing — always offsets, never text, ours or not.
            row["parallel"] = blurb_shelf.phrase_record(
                defense["parallel"], blurb_shelf.page(named), is_ours=False
            )
            row["parallel_from"] = blurb_shelf.digest_of(blurb_shelf.page(named))
        if outcome != "valid":
            surviving += 1
        rows.append(row)
    return {
        "words": len(listing.split()),
        "draws": len(draw_flags),
        "unique_flags": len(capped),
        "dropped_over_cap": len(collected["flags"]) - len(capped),
        "unlocated_flags": collected["unlocated"],
        "defenses_answered": answered,
        "defenses_missing": len(capped) - answered,
        "valid_defenses": valid,
        "fabricated_defenses": fabricated,
        "ka_rate": (fabricated / answered) if answered else None,
        "surviving_flags": surviving,
        "flags_per_100_words": len(capped) / words * 100,
        "surviving_per_100_words": surviving / words * 100,
        "kd": flag_agreement(draw_token_sets(draw_flags, listing)),
        "flags": rows,
    }


# ------------------------------------------------------------------------------ kill conditions


def kills(
    kd_by_leg: dict[str, float | None], ka_by_leg: dict[str, float | None]
) -> dict[str, Any]:
    """The control table. Directions and distributions; no bars anywhere.

    KD per leg against the registered floor: a measurement leg below it means the flagger
    disagrees with itself draw to draw and nothing downstream is readable. KA is reported per
    leg, direction only — an advocate that fabricates constantly collapses the mechanism
    toward everything-surviving, and the rate is the number that says so. KG lives beside them
    in the results; until it separates, nothing here says anything about ours.
    """

    def kd_verdict(value: float | None) -> str:
        return (
            "UNREADABLE" if value is None else ("NOISE" if value < KD_AGREEMENT_FLOOR else "PASS")
        )

    return {
        "KD": {
            "floor": KD_AGREEMENT_FLOOR,
            "by_leg": kd_by_leg,
            "verdict": {leg: kd_verdict(value) for leg, value in kd_by_leg.items()},
        },
        "KA": {
            "by_leg": ka_by_leg,
            "reading": "direction only, no bar: higher fabrication weakens every survival",
        },
    }


def mirrored_gradient_stat(
    pairs_low_high: list[tuple[float, float]],
    *,
    draws: int = BOOTSTRAP_DRAWS,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """`blurb_rewrite.gradient_stat`'s seeded construction, mirrored because the import was
    unavailable. Identical statistic, identical seed discipline; the registration records
    which implementation produced a given run's KG."""
    if not pairs_low_high:
        return {"pairs": 0}
    wins = sum(low > high for low, high in pairs_low_high)
    rng = random.Random(seed)
    n = len(pairs_low_high)
    boots: list[float] = []
    for _ in range(draws):
        sample = (pairs_low_high[rng.randrange(n)] for _ in range(n))
        boots.append(sum(low > high for low, high in sample) / n)
    boots.sort()
    lo = boots[int(0.025 * draws)]
    hi = boots[min(int(0.975 * draws), draws - 1)]
    return {
        "pairs": n,
        "wins": wins,
        "share": wins / n,
        "bootstrap_interval": [lo, hi],
        "per_pair_delta": [low - high for low, high in pairs_low_high],
    }


def kg_statistic(pairs_low_high: list[tuple[float, float]]) -> dict[str, Any]:
    """KG through the registered implementation — imported when possible, mirrored otherwise."""
    stat = (
        gradient_stat(pairs_low_high)
        if gradient_stat is not None
        else mirrored_gradient_stat(pairs_low_high)
    )
    stat["implementation"] = "imported" if gradient_stat is not None else "mirrored"
    return stat


def selftest() -> int:
    """The free leg: every registered definition on inputs whose answers are hand-stated."""
    failures: list[str] = []

    def _row(index: int, words: int) -> dict[str, Any]:
        listing = " ".join(f"w{index}t{token}" for token in range(words))
        return {
            "title": f"Title {index}",
            "listing": f"{listing}.",
            "followers": 1000 - index,
            "source": f"high{index}",
        }

    high = [_row(i, 40 + i) for i in range(30)]

    rendered = render_flag_prompt(high[:N_REFERENCES], high[9])
    blocks = rendered.split("\n\n===\n\n")
    if len(blocks) != N_REFERENCES + 1 or not blocks[-1].startswith("THE LISTING UNDER READING:"):
        failures.append("the flag prompt renders five numbered references and the target block")
    if ASK_FLAG not in rendered or blurb_shelf.page(high[9]) not in rendered:
        failures.append("the flag prompt must carry the frozen ask and the target's page")
    defend_rendered = render_defend_prompt(high[:N_REFERENCES], "x y")
    if ASK_DEFEND.format(phrase="x y") not in defend_rendered or "w9t0" in defend_rendered:
        failures.append("the defend prompt carries the phrase alone and never the target")

    shelf = reference_shelf(high, high[3])
    if len(shelf) != N_REFERENCES or any(identity(r) == identity(high[3]) for r in shelf):
        failures.append("a reference shelf holds five HIGH rows and never the target itself")
    if [identity(r) for r in reference_shelf(high, high[3])] != [identity(r) for r in shelf]:
        failures.append("the reference shelf must be deterministic")

    low_rows = [
        {"title": f"Low {i}", "listing": " ".join(f"l{i}w{t}" for t in range(42)) + ".",
         "followers": 3, "source": f"low{i}"}
        for i in range(6)
    ]
    built = build_targets(high, low_rows, 4, 4, [])
    gradient_pairs = {t["pair"] for t in built if t["leg"] == "gradient"}
    sham_pairs = {t["pair"] for t in built if t["leg"] == "sham" and t["pair"] is not None}
    if len(gradient_pairs) != 4 or gradient_pairs != sham_pairs:
        failures.append(
            "every gradient pair's HIGH partner carries the pair index, plain sham or not — "
            "a partner without it drops its pair from KG silently"
        )

    if parse_flags('{"flags":["a b"],"extra":1}') is not None:
        failures.append("an extra key must be a refusal, not partial credit")
    if parse_flags('{"flags":"x"}') is not None or parse_flags('{"flags":[7]}') is not None:
        failures.append("a non-list flags field and a non-string flag are refusals")
    if parse_flags(json.dumps({"flags": ["ok"] * (FLAG_MAX_ITEMS + 1)})) is not None:
        failures.append("more than FLAG_MAX_ITEMS flags must be a refusal")
    if parse_flags("not json") is not None or parse_flags("") is not None:
        failures.append("non-JSON and empty answers are refusals")
    if parse_flags('{"flags": ["  a   b  ", ""]}') != ["a b"]:
        failures.append("flags are whitespace-collapsed and blanks dropped")

    if parse_defense('{"parallel":"","from_listing":2}') is not None:
        failures.append("shape one malformed: a named listing demands a non-empty quote")
    if parse_defense('{"parallel":"a b","from_listing":0}') is not None:
        failures.append("shape two malformed: 0 pairs only with an empty quote")
    if parse_defense('{"parallel":"a","from_listing":6}') is not None:
        failures.append("a listing number above five must be a refusal")
    if parse_defense('{"parallel":"a","from_listing":true}') is not None:
        failures.append("a boolean listing number must be a refusal")
    if parse_defense('{"parallel":"a b","from_listing":2,"x":0}') is not None:
        failures.append("an extra key in a defense must be a refusal")
    if parse_defense('{"parallel":"","from_listing":0}') != {"parallel": "", "from_listing": 0}:
        failures.append("the well-formed zero defense must parse")

    target_listing = "the ward held through the gate and his mana was a patch of notes."
    draws = [
        ["patch of notes", "wholly absent phrase"],
        ["patch of notes"],
        ["patch of notes", "ward held"],
        [],
    ]
    collected = collect_flags(draws, target_listing)
    if collected["unlocated"] != 1:
        failures.append("a fabricated quotation must be dropped and counted, never kept")
    keys = [row["key"] for row in collected["flags"]]
    if keys != ["patch of notes", "ward held"]:
        failures.append("dedupe merges across draws and orders by support")
    if collected["flags"][0]["support"] != 3 or collected["flags"][1]["support"] != 1:
        failures.append("a flag's row carries how many draws produced it")

    refs = [_row(100 + i, 41) for i in range(N_REFERENCES)]
    refs[1]["listing"] = "a construction that works the same way appears here."
    # Defenses are keyed by each flag's dedupe key, exactly as `run` feeds them.
    defenses = {
        "patch of notes": {"parallel": "works the same way", "from_listing": 2},
        "ward held": {"parallel": "never written anywhere at all", "from_listing": 1},
    }

    def _runs(defs: dict[str, dict[str, Any] | None]) -> dict[str, Any]:
        return tribunal(target_listing, draws, defs, refs, is_ours=False)

    killed = _runs(defenses)
    if killed["valid_defenses"] != 1 or killed["fabricated_defenses"] != 1:
        failures.append("the third seat must separate a locating parallel from a fabricated one")
    outcomes = sorted(row["outcome"] for row in killed["flags"])
    if outcomes != ["fabricated", "valid"]:
        failures.append("a valid defense kills its flag; a fabricated one does not")
    if killed["ka_rate"] != 0.5 or killed["defenses_answered"] != 2:
        failures.append("KA is fabricated over answered defenses, failures excluded")
    expected = 100 * 1 / len(target_listing.split())
    if killed["surviving_flags"] != 1 or abs(killed["surviving_per_100_words"] - expected) > 1e-9:
        failures.append("survival divides by the listing's own word count")

    no_kill = _runs(dict.fromkeys(defenses))
    if no_kill["surviving_flags"] != 2 or no_kill["ka_rate"] is not None:
        failures.append("missing defenses kill nothing and stay out of KA")
    if no_kill == killed:
        failures.append("two different targets' mechanisms must stay two summaries")
    if "ONE target" not in (tribunal.__doc__ or ""):
        failures.append("the per-target function must say it takes one target's rows, never two")
    if next(iter(inspect.signature(tribunal).parameters)) != "listing":
        failures.append("the tribunal's first parameter is one listing — there is no pooler")

    market_row = json.dumps(_runs(defenses)["flags"])
    if "patch of notes" in market_row or "works the same way" in market_row:
        failures.append("a market-target row carries offsets, never third-party prose")
    ours = tribunal(target_listing, draws, {}, refs, is_ours=True)
    if ours["flags"][0]["flag"].get("verbatim") != "patch of notes":
        failures.append("an ours-target flag row is stored verbatim")

    sets = [frozenset("ab"), frozenset("ab"), frozenset("cd"), frozenset()]
    if abs((flag_agreement(sets) or 0) - 1 / 6) > 1e-9:
        failures.append("KD is mean pairwise Jaccard over the draws' token sets")

    table = kills({"gradient": 0.7, "sham": 0.4}, {"gradient": 0.25, "sham": None})
    if table["KD"]["verdict"] != {"gradient": "PASS", "sham": "NOISE"}:
        failures.append("KD must verdict each leg against the floor, never a pooled number")
    if table["KA"]["by_leg"]["sham"] is not None:
        failures.append("KA reports None when a leg answered nothing")

    stat = kg_statistic([(0.60, 0.20), (0.50, 0.30), (0.40, 0.35)])
    if stat["wins"] != 3 or stat["share"] != 1.0:
        failures.append("KG counts the pairs where LOW survives more than HIGH")
    if registration_digest() != registration_digest():
        failures.append("registration digest unstable")

    for line in failures:
        print(f"FAIL {line}", file=sys.stderr)
    print("selftest: " + ("FAILED" if failures else "passed"), file=sys.stderr)
    return 1 if failures else 0


# ------------------------------------------------------------------------------------ the run


def _complete(registry: Any, prompt: str, schema: dict[str, Any]) -> Any:
    """One measurement request, the conventions of the sibling instruments."""
    from litharness.domain.generation import CompletionRequest

    request = CompletionRequest(
        prompt=prompt,
        system=SYSTEM,
        schema=schema,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        profile=PROFILE,
        call_class="generation",
        timeout_seconds=300.0,
    )
    result, _ = registry.complete(request)
    return result


def _parsed_payload(result: Any) -> str:
    parsed = getattr(result, "parsed", None)
    return json.dumps(parsed) if isinstance(parsed, dict) else ""


def run(
    registry: Any, targets: list[dict[str, Any]], high: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Stage 1 (K draws per target), then stage 2 (once per unique located flag, capped).

    Returns the per-target reports and the raw sidecar payload. Transport failures are
    excluded from every rate and counted, never scored — the standing rule.
    """
    transport = {"flag_calls": 0, "defend_calls": 0}
    reports: dict[str, Any] = {}
    raw_draws_by_target: dict[str, Any] = {}
    for target in targets:
        refs = reference_shelf(high, target["row"])
        listing = str(target["row"]["listing"])
        draw_flags: list[list[str]] = []
        raw_draws: list[Any] = []
        for _ in range(K_DRAWS):
            try:
                result = _complete(registry, render_flag_prompt(refs, target["row"]), FLAG_SCHEMA)
            except Exception as error:  # an outage is a fact about the day, not about the text
                transport["flag_calls"] += 1
                raw_draws.append(str(error)[:160])
                continue
            answer = parse_flags(_parsed_payload(result))
            raw_draws.append(answer)
            if answer is not None:
                draw_flags.append(answer)

        collected = collect_flags(draw_flags, listing)
        defenses: dict[str, dict[str, Any] | None] = {}
        raw_defenses: dict[str, Any] = {}
        for flag in collected["flags"][:FLAG_MAX_ITEMS]:
            try:
                result = _complete(
                    registry, render_defend_prompt(refs, flag["phrase"]), DEFEND_SCHEMA
                )
            except Exception as error:  # excluded from every rate; counted, never scored
                transport["defend_calls"] += 1
                defenses[flag["key"]] = None
                raw_defenses[flag["key"]] = str(error)[:160]
                continue
            answer = parse_defense(_parsed_payload(result))
            defenses[flag["key"]] = answer
            raw_defenses[flag["key"]] = answer
        report = tribunal(listing, draw_flags, defenses, refs, is_ours=target["leg"] == "ours")
        report["references"] = [blurb_shelf.digest_of(blurb_shelf.page(row)) for row in refs]
        if target["leg"] == "ours":
            report["title"] = str(target["row"].get("title") or "")
            report["listing"] = listing
        reports[target["name"]] = {"leg": target["leg"], "pair": target["pair"], **report}
        raw_draws_by_target[target["name"]] = {"draws": raw_draws, "defenses": raw_defenses}
    return reports, {"transport_failures": transport, "raw": raw_draws_by_target}


def plan_calls(targets: list[dict[str, Any]]) -> tuple[int, int]:
    """(exact stage-1 calls, worst-case stage-2 calls) for a built target list."""
    return K_DRAWS * len(targets), FLAG_MAX_ITEMS * len(targets)


# ------------------------------------------------------------------------------------ the CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument(
        "--pool",
        nargs=2,
        default=[str(DERIVED / "rivals.json"), str(DERIVED / "rivals-low.json")],
        help="derived/ pools, HIGH then LOW, read as blurb_gradient reads them",
    )
    parser.add_argument("--texts", nargs="*", default=[], help="ours, `listing_arena.load_texts`")
    parser.add_argument("--shams", type=int, default=DEFAULT_SHAMS)
    parser.add_argument("--pairs", type=int, default=DEFAULT_PAIRS)
    parser.add_argument("--out", type=Path, default=RESULTS / "blurb-tribunal.json")
    parser.add_argument("--yes", action="store_true")
    # Undocumented on purpose: the parent session runs the gated run. An operator typing this
    # flag by accident is not the failure mode being guarded; unattended quota spend is.
    parser.add_argument("--i-am-the-gated-run", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.dry_run and not args.run:
        parser.error("pass one of --selftest, --dry-run, --run")

    # The gate reads nothing and loads nothing: the guard is checked against the registered
    # conservative bound (every pair's partner an extra sham) before any spend is possible.
    bound_targets = args.shams + 2 * args.pairs + len(args.texts)
    bound_total = (K_DRAWS + FLAG_MAX_ITEMS) * bound_targets
    if args.run and bound_total > CALL_GUARD and not args.yes:
        print(
            f"{bound_total} worst-case calls exceeds the {CALL_GUARD} guard; pass --yes",
            file=sys.stderr,
        )
        return 1
    if args.run and not args.i_am_the_gated_run:
        print(
            "refusing: --run needs --i-am-the-gated-run; this spend is gated on the operator",
            file=sys.stderr,
        )
        return 1

    high = json.loads(Path(args.pool[0]).read_text(encoding="utf-8"))
    low = json.loads(Path(args.pool[1]).read_text(encoding="utf-8"))
    placeholder_texts = [
        {"name": Path(path).stem, "title": "", "listing": ""} for path in args.texts
    ]
    targets = build_targets(high, low, args.shams, args.pairs, placeholder_texts)
    stage_one, stage_two_worst = plan_calls(targets)

    if args.dry_run:
        legs: dict[str, int] = {}
        for target in targets:
            legs[target["leg"]] = legs.get(target["leg"], 0) + 1
        detail = ", ".join(f"{count} {leg}" for leg, count in sorted(legs.items()))
        print(f"targets: {len(targets)} ({detail})")
        print(f"stage 1: {stage_one} calls exactly: K={K_DRAWS} x {len(targets)} target(s)")
        print(
            f"stage 2: between 0 and {stage_two_worst} calls (worst case first): at most "
            f"{FLAG_MAX_ITEMS} defense(s) x {len(targets)} target(s)"
        )
        print(
            f"total: between {stage_one} and {stage_one + stage_two_worst} calls, worst case first"
        )
        print("dry run: no registry constructed, nothing spent", file=sys.stderr)
        return 0

    from litharness.providers import build_default_registry  # lazy: heavy, paid path only

    texts = listing_arena.load_texts(args.texts)
    targets = build_targets(high, low, args.shams, args.pairs, texts)
    stage_one, stage_two_worst = plan_calls(targets)
    print(
        f"{len(targets)} target(s): {args.shams} shams, {args.pairs} gradient pairs, "
        f"{len(texts)} ours"
    )

    reports, raw = run(build_default_registry(), targets, high)

    kd_by_leg: dict[str, list[float]] = {}
    ka_by_leg: dict[str, list[float]] = {}
    for report in reports.values():
        if report["kd"] is not None:
            kd_by_leg.setdefault(report["leg"], []).append(report["kd"])
        if report["ka_rate"] is not None:
            ka_by_leg.setdefault(report["leg"], []).append(report["ka_rate"])
    legs_kd = {leg: statistics.fmean(values) for leg, values in sorted(kd_by_leg.items())}
    legs_ka = {leg: statistics.fmean(values) for leg, values in sorted(ka_by_leg.items())}

    # KG: build_targets guarantees both sides of every pair were measured, so the pair
    # statistic reads surviving_per_100_words(LOW) against surviving_per_100_words(HIGH).
    pair_values = {
        (report["pair"], report["leg"]): report["surviving_per_100_words"]
        for report in reports.values()
        if report["pair"] is not None
    }
    kg_pairs = [
        (low_value, pair_values[(pair, "sham")])
        for (pair, leg), low_value in sorted(pair_values.items())
        if leg == "gradient" and (pair, "sham") in pair_values
    ]
    kg = kg_statistic(kg_pairs)

    result = {
        "study": BLURB_TRIBUNAL_VERSION,
        "registration": "plan/blurb-tribunal-validity.md",
        "registration_digest": registration_digest(),
        # Read before any verdict, the standing rule: a failed call was excluded from every
        # rate, and a run with many of them is a fact about the day rather than the text.
        "transport_failures": raw["transport_failures"],
        "calls_planned": {"stage_one": stage_one, "stage_two_worst": stage_two_worst},
        "targets": reports,
        "kills": {**kills(legs_kd, legs_ka), "KG": kg},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
    # Raw flags and parallels — full text for every target — live under derived/, which
    # .gitignore covers; the committed record carries phrase_record rows only.
    DERIVED.mkdir(parents=True, exist_ok=True)
    (DERIVED / f"{args.out.stem}-raw.json").write_text(
        json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    for name, report in reports.items():
        print(
            f"  {name:34} {report['leg']:9} survived "
            f"{report['surviving_flags']}/{report['unique_flags']}"
        )
    print(
        f"KG gradient: LOW above HIGH in {kg.get('wins', 0)}/{kg.get('pairs', 0)} pair(s), "
        f"share {kg.get('share')}"
    )
    print(f"KD per leg: {legs_kd}")
    print(f"KA per leg: {legs_ka}")
    print(
        f"transport failures: {raw['transport_failures']['flag_calls']} flag call(s), "
        f"{raw['transport_failures']['defend_calls']} defend call(s) — read before any verdict"
    )
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
