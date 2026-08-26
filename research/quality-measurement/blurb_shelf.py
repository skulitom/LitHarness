"""Put one listing that does not belong on a shelf of real ones, and see who is named.

Task 3 of `plan/handoff-reader-perception.md`. Every probe so far asked a model to judge from
memory; a reader shown five real listings from this market *and then* a sixth has a concrete
reference rather than a recalled one. So this module does not ask for a rating anywhere. It
asks a **detection question with a right answer**: one of these six was not written by this
market's writers — which, and quote the phrase that tells you — with a sham floor beside it
(a shelf where nothing is wrong) so that a detection rate means something. Nothing rates,
ranks or compares, which is what keeps this outside the six dead judgment probes (boundary 5)
and outside the settled pick-between-two (boundary 2).

Three legs, every shelf built by a seeded deterministic shuffle (seed derived from a content
digest; never the global `random`, never time):

- **Sham shelves** — six HIGH listings, top of the admitted pool by followers. The
  false-alarm floor, **per sham and never pooled** (the persona-battery rule).
- **Gradient leg (KG)** — five HIGH + one LOW, length-matched (`blurb_gradient`'s pools and
  pairing). Detection here is the instrument's validity check (§141's H = 0.935 is the bar
  this readership already cleared once).
- **Ours leg** — five HIGH + one of ours (`--texts`). Plus the quoted phrases: the located
  diagnosis the operator has been supplying by hand.

And the controls: **KP** (position — a sham whose false alarms track one slot is a position
kill), **KS** (surface — a shelf whose sixth listing differs only by being truncated to the
LOW leg's median length; if truncation alone detects at gradient-leg rates the instrument is
reading length and is dead), **KD** (draw reliability — cross-draw agreement, gate-0 shape).

**Results carry no third-party prose.** Shelf composition is stored as row digests and slot
order. A quoted phrase is stored verbatim only when the named slot holds one of OUR listings;
for any other slot the row carries the phrase's token offsets into that listing plus a
`located` flag — locvisable by digest, never the market's text. `phrase_record` is the single
choke point that enforces this.

Free legs first; the paid run is refused without both `--yes` and the undocumented
`--i-am-the-gated-run`:

    uv run python research/quality-measurement/blurb_shelf.py --selftest
    uv run python research/quality-measurement/blurb_shelf.py --dry-run \
        --pool derived/rivals.json --low derived/rivals-low.json --texts pilot7/listing.json

The package interpreter, because this reads no corpus: the pools arrive as files that
`rival_pool.py` wrote, ours as `listing_arena.load_texts` bundles.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import sys
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "src"))

DERIVED = HERE / "derived"
RESULTS = HERE / "results"

# ---------------------------------------------------------------- the registration, frozen

#: v0.1, and the two changes from v0 are construction findings from its first run
#: (`results/blurb-shelf.json`, the registration's amendment section): sham shelves now
#: re-shuffle per draw so a reader consistently naming the same LISTING no longer fixes a
#: slot (v0's KP could not tell identity from position on a static shelf), and KD is read
#: per leg (v0 pooled shams with measurement legs, two different tasks under one number).
BLURB_SHELF_VERSION = "blurb_shelf.v0.1"

#: Listings per shelf, numbered 1-6 in the ask.
SHELF_SIZE = 6

#: Draws per shelf; the target's slot rotates across them (at least 4 of the 6 slots per
#: target). Four is the comic-beat census's lesson applied, as in `anticipation.py`.
K_DRAWS = 4

#: Leg sizes, all small on purpose: the free legs prove the arithmetic before anything spends.
SHAM_SHELVES = 6
GRADIENT_PAIRS = 8
SURFACE_SHELVES = 4

#: Refuse above this many calls without --yes.
CALL_GUARD = 500

#: Requests carry the measurement profile/call_class conventions (`listing_arena.py` through
#: `blurb_perception.py`): a named profile, the generation class, a bounded timeout.
PROFILE = "reader.shelf.v0"
MAX_OUTPUT_TOKENS = 400

#: **Byte-frozen.** A persona, not a judge: years on this market, and then a detection task.
SYSTEM = "You have read serial fiction on this market for years."

#: **Byte-frozen.** The ask names the task, demands the locating phrase, and allows "none".
ASK = (
    "These six listings are from one shelf of this market. If one of them reads as though it "
    "was not written by this market's writers, answer with its number and quote the exact "
    "phrase that tells you. If none does, answer 0."
)

#: **Byte-frozen.** Two fields, closed: the number and the phrase. No rating, no ranking, no
#: reason slot; the phrase is empty exactly when nothing is named.
ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["off_shelf", "phrase"],
    "additionalProperties": False,
    "properties": {
        "off_shelf": {"type": "integer", "minimum": 0, "maximum": SHELF_SIZE},
        "phrase": {
            "type": "string",
            "description": (
                "Quote the exact phrase that tells you. Empty string if you answered 0."
            ),
        },
    },
}

#: KP's definition, registered: a shelf's false alarms track one slot when at least half of
#: its non-zero answers name that same slot (and there are at least two to speak of).
KP_MODAL_SHARE = 0.5

#: KD's floor, registered: below this mean cross-draw agreement the draws disagree with each
#: other more than they agree, and no direction is readable from any leg (gate-0 discipline).
KD_AGREEMENT_FLOOR = 0.5

PRE_REGISTRATION: dict[str, Any] = {
    "version": BLURB_SHELF_VERSION,
    "system": SYSTEM,
    "ask": ASK,
    "schema": ANSWER_SCHEMA,
    "shelf_size": SHELF_SIZE,
    "k_draws": K_DRAWS,
    "sham_shelves": SHAM_SHELVES,
    "gradient_pairs": GRADIENT_PAIRS,
    "surface_shelves": SURFACE_SHELVES,
    "call_guard": CALL_GUARD,
    "kp_modal_share": KP_MODAL_SHARE,
    "kd_agreement_floor": KD_AGREEMENT_FLOOR,
}


def registration_digest() -> str:
    material = json.dumps(PRE_REGISTRATION, sort_keys=True, ensure_ascii=False)
    return sha256(material.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------- deterministic parts


def digest_of(text: str) -> str:
    return sha256(text.encode()).hexdigest()[:12]


def seed_of(*parts: Any) -> int:
    """An integer seed from a content digest — deterministic, never time, never unseeded."""
    material = "|".join(str(part) for part in parts)
    return int.from_bytes(sha256(material.encode("utf-8")).digest()[:8], "big")


def seeded_order(rows: list[Any], seed: int) -> list[Any]:
    """A shuffled copy under an explicitly seeded generator; the global `random` is untouched."""
    rng = random.Random(seed)
    order = list(rows)
    rng.shuffle(order)
    return order


# ------------------------------------------------------------------------ shelf construction


def page(row: dict[str, Any]) -> str:
    """The rendered listing: title, blank line, listing — `blurb_gradient.page`'s shape."""
    return f"{str(row['title']).strip()}\n\n{str(row['listing']).strip()}"


def render_shelf(rows: list[dict[str, Any]]) -> str:
    """Six numbered pages, ``===``-separated, then the frozen ask.

    The rendering carries listing text and slot numbers only — the results side identifies
    rows by digest, and this string must never embed one.
    """
    blocks = [f"{number}. {page(row)}" for number, row in enumerate(rows, start=1)]
    return "\n\n===\n\n".join(blocks) + f"\n\n===\n\n{ASK}"


def matched_pairs(
    high: list[dict[str, Any]], low: list[dict[str, Any]], count: int
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Each HIGH paired with the nearest unused LOW by word count.

    Copied from `blurb_gradient.matched_pairs` — that pairing is its registered construction
    and this module does not reinvent it.
    """
    ranked = sorted(high, key=lambda row: -int(row["followers"] or 0))[:count]
    spare = list(low)
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for top in ranked:
        want = len(str(top["listing"]).split())
        spare.sort(key=lambda row: abs(len(str(row["listing"]).split()) - want))
        if not spare:
            break
        pairs.append((top, spare.pop(0)))
    return pairs


def ranked_by_followers(pool: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(pool, key=lambda row: -int(row["followers"] or 0))


def nearest_high(
    high: list[dict[str, Any]], want_words: int, count: int
) -> list[dict[str, Any]]:
    """The `count` HIGH listings closest in word count; ties break by rank, then source.

    Length-matching a whole shelf around its target means word count cannot be the tell
    anywhere on that shelf — the strongest available form of the KS guard on the gradient leg.
    """
    return sorted(
        high,
        key=lambda row: (
            abs(len(str(row["listing"]).split()) - want_words),
            -int(row["followers"] or 0),
            str(row.get("source") or ""),
        ),
    )[:count]


_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def truncate_to_word_count(text: str, target_words: int) -> str:
    """A prefix of whole sentences whose word count does not exceed `target_words`.

    Code-built surface damage, no model: the first sentence always survives (a shelf slot is
    never emptied) and no sentence is cut mid-way — a partial sentence would smuggle a second
    tell into the KS control.
    """
    sentences = [s for s in _SENTENCE_BOUNDARY.split(text.strip()) if s.strip()]
    kept: list[str] = []
    count = 0
    for sentence in sentences:
        words = len(sentence.split())
        if kept and count + words > target_words:
            break
        kept.append(sentence)
        count += words
    return " ".join(kept)


def build_sham_shelves(pool: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    """`count` all-HIGH shelves from the top of the admitted pool, seeded per shelf."""
    top = ranked_by_followers(pool)[: 6 * count]
    shelves: list[dict[str, Any]] = []
    for index in range(count):
        rng = random.Random(seed_of(BLURB_SHELF_VERSION, "sham", index))
        members = rng.sample(top, min(SHELF_SIZE, len(top)))
        shelves.append(
            {"leg": "sham", "name": f"sham_{index}", "members": members, "target": None}
        )
    return shelves


def build_gradient_shelves(
    high: list[dict[str, Any]], low: list[dict[str, Any]], count: int
) -> list[dict[str, Any]]:
    """Five HIGH + one LOW: the LOW roster in `matched_pairs` order, each shelf length-matched."""
    shelves: list[dict[str, Any]] = []
    for index, (_, target) in enumerate(matched_pairs(high, low, count)):
        want = len(str(target["listing"]).split())
        shelves.append(
            {
                "leg": "gradient",
                "name": f"gradient_{index}",
                "fillers": nearest_high(high, want, SHELF_SIZE - 1),
                "target": target,
            }
        )
    return shelves


def build_ours_shelves(
    high: list[dict[str, Any]], texts: list[dict[str, str]]
) -> list[dict[str, Any]]:
    """Five HIGH + one of ours, the shelf length-matched around ours as the gradient leg is.

    The same construction as `build_gradient_shelves`, deliberately: the validation leg
    excludes length as a tell by matching fillers to its target, so the leg whose reading
    matters must be built the same way or the validation does not transfer (the registration
    records the amendment).
    """
    shelves: list[dict[str, Any]] = []
    for index, entry in enumerate(texts):
        want = len(str(entry["listing"]).split())
        shelves.append(
            {
                "leg": "ours",
                "name": f"ours_{index}:{entry['name']}",
                "fillers": nearest_high(high, want, SHELF_SIZE - 1),
                "target": entry,
            }
        )
    return shelves


def build_surface_shelves(
    high: list[dict[str, Any]], low: list[dict[str, Any]], count: int
) -> list[dict[str, Any]]:
    """Five full-length HIGH + one HIGH truncated to the LOW leg's median word count.

    The truncated slot differs only by being shorter. If truncation alone is detected at
    gradient-leg rates, the instrument reads length and is dead.
    """
    median_words = int(statistics.median(len(str(r["listing"]).split()) for r in low))
    ranked = ranked_by_followers(high)
    shelves: list[dict[str, Any]] = []
    for index in range(count):
        victim = ranked[index % len(ranked)]
        shortened = {
            "title": victim["title"],
            "listing": truncate_to_word_count(str(victim["listing"]), median_words),
        }
        others = [row for row in ranked if row is not victim]
        shelves.append(
            {
                "leg": "surface",
                "name": f"surface_{index}",
                "fillers": nearest_high(others, len(str(victim["listing"]).split()), 5),
                "target": shortened,
                "truncated_to_words": median_words,
            }
        )
    return shelves


def slot_placement(
    fillers: list[dict[str, Any]], target: dict[str, Any], slot: int
) -> list[dict[str, Any]]:
    """The six rows with the target dropped into `slot` (0-based); fillers keep their order."""
    return [*fillers[:slot], target, *fillers[slot : SHELF_SIZE - 1]]


def target_start_slot(shelf_name: str) -> int:
    """The deterministic slot the target occupies on draw 0; draws rotate onward mod 6."""
    return seed_of(BLURB_SHELF_VERSION, shelf_name, "slots") % SHELF_SIZE


# ------------------------------------------------------------------------------- the scorers


def parse_answer(text: str) -> dict[str, Any] | None:
    """`{"off_shelf": 0-6, "phrase": str}` exactly, else None — one shape, no partial credit.

    Non-JSON, wrong keys, extra keys, an out-of-range slot, a phrase beside a 0, or a bare
    number without its locating phrase are all the same None; folding a malformed answer into
    the tally would score the format, not the detection.
    """
    if not text:
        return None
    try:
        payload = json.loads(text)
    except ValueError:
        return None
    if not isinstance(payload, dict) or set(payload) != {"off_shelf", "phrase"}:
        return None
    slot = payload["off_shelf"]
    phrase = payload["phrase"]
    if isinstance(slot, bool) or not isinstance(slot, int) or not 0 <= slot <= SHELF_SIZE:
        return None
    if not isinstance(phrase, str):
        return None
    if bool(slot) != bool(phrase.strip()):  # 0 pairs with empty; a number demands its quote
        return None
    return {"off_shelf": slot, "phrase": phrase.strip()}


def tally_draws(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Detection counting over one shelf's draw records.

    Each record carries `named_slot` (1-6, or None when refused/unparseable) and, for legs
    with a target, `target_slot`. A hit names the target's own slot; `detection` is the share
    of answered draws that hit; `by_slot` reports draws and hits per target slot so position
    can be read next to every rate.
    """
    answered = [r for r in records if r.get("named_slot") is not None]
    hits = [r for r in answered if r.get("target_slot") == r["named_slot"]]
    zeros = [r for r in answered if r["named_slot"] == 0]
    by_slot: dict[str, dict[str, int]] = {}
    for record in answered:
        bucket = by_slot.setdefault(str(record.get("target_slot")), {"draws": 0, "hits": 0})
        bucket["draws"] += 1
        if record.get("target_slot") == record["named_slot"]:
            bucket["hits"] += 1
    return {
        "draws": len(records),
        "answered": len(answered),
        "refused": len(records) - len(answered),
        "hits": len(hits),
        "zeros": len(zeros),
        "detection": (len(hits) / len(answered)) if answered else None,
        "by_slot": by_slot,
    }


def sham_floor(records: list[dict[str, Any]]) -> dict[str, Any]:
    """ONE sham shelf's false-alarm floor, from that shelf's rows alone — NEVER pooled.

    The persona-battery rule, restated for shelves: a floor computed across shams would let
    one slot-happy sham hide inside the average of its neighbours. Every caller passes a
    single sham's records; there is no function anywhere in this module that accepts two.
    """
    named = [r["named_slot"] for r in records if r.get("named_slot")]
    histogram = Counter(named)
    modal_slot: int | None = None
    modal_count = 0
    if histogram:
        modal_slot = max(histogram, key=lambda s: (histogram[s], -int(s)))
        modal_count = histogram[modal_slot]
    # v0.1: the modal LISTING beside the modal slot. With per-draw re-shuffling the two come
    # apart — a reader repeatedly flagging one listing is consistency (reported, killed by
    # nothing), and only a slot that stays modal across re-shuffles is position (KP).
    digests = [r.get("named_digest") for r in records if r.get("named_slot")]
    digest_counts = Counter(d for d in digests if d)
    modal_listing_share = (
        max(digest_counts.values()) / len(digests) if digest_counts and digests else None
    )
    return {
        "draws": len(records),
        "named": len(named),
        "false_alarm": (len(named) / len(records)) if records else None,
        "by_slot": {slot: histogram[slot] for slot in sorted(histogram)},
        "modal_slot": modal_slot,
        "modal_share": (modal_count / len(named)) if named else None,
        "modal_listing_share": modal_listing_share,
        "position_kill": len(named) >= 2 and (modal_count / len(named)) >= KP_MODAL_SHARE,
    }


def draw_agreement(answers: list[int | None]) -> float | None:
    """Cross-draw agreement within one shelf: the share of answered draws naming the mode.

    KD reads this, gate-0 shape — draws that disagree with each other as much as they agree
    make every rate above noise wearing a number.
    """
    answered = [a for a in answers if a is not None]
    if not answered:
        return None
    counts = Counter(answered)
    return max(counts.values()) / len(answered)


# ------------------------------------------------------- the quoted phrase, and what may be kept

_PUNCTUATION = ".,;:!?()[]{}\"'\u201c\u201d\u2018\u2019\u2014\u2013\u2026"


def _tokens(text: str) -> list[str]:
    return [token.strip(_PUNCTUATION).casefold() for token in text.split()]


def locate_tokens(phrase: str, listing: str) -> list[int] | None:
    """[start, end) token offsets of the phrase inside the listing, or None when absent.

    Token offsets, not characters: a reader of the results file can land on the span from any
    copy of the listing it locates by digest, without this module storing a character map.
    """
    wanted = [t for t in _tokens(phrase) if t]
    if not wanted:
        return None
    tokens = _tokens(listing)
    size = len(wanted)
    for start in range(len(tokens) - size + 1):
        if tokens[start : start + size] == wanted:
            return [start, start + size]
    return None


def phrase_record(phrase: str, listing: str, *, is_ours: bool) -> dict[str, Any]:
    """The single choke point through which a quoted phrase enters a result row.

    A phrase quoted off one of OUR listings is stored verbatim — that is the located
    diagnosis the operator has been supplying by hand. For ANY other slot the market's text
    does not pass: the row carries token offsets into that listing plus a `located` flag,
    and nothing else. Nothing else in this module touches `phrase` bytes.
    """
    cleaned = " ".join(phrase.split())
    span = locate_tokens(cleaned, listing)
    if not is_ours:
        if span is None:
            return {"located": False}
        return {"token_offsets": span, "located": True}
    return {"verbatim": cleaned, "token_offsets": span, "located": span is not None}


# ------------------------------------------------------------------------------ kill conditions


def kills(sham_floors: list[dict[str, Any]], legs: dict[str, Any]) -> dict[str, Any]:
    """The three registered kills, each verdict naming its numbers.

    KP — position: fires when ANY single sham's false alarms track one slot (`position_kill`
    in its own floor; meaningful because v0.1 re-shuffles a sham per draw, so only position
    can keep a slot modal). KS — surface: truncation-only shelves detected at gradient-leg
    rates means the instrument reads length, and is dead; direction only, no bar over either
    rate. KD — draw reliability per leg, each against the registered floor: a measurement
    leg below it is unreadable; a sham's number is reported for what it is (draws on a
    re-shuffled shelf with nothing to find should scatter). No bar over any detection rate.
    """
    worst = max((floor["modal_share"] or 0.0) for floor in sham_floors) if sham_floors else None
    kp = {
        "worst_modal_share": worst,
        "verdict": (
            "UNREADABLE"
            if not sham_floors
            else ("KILL" if any(floor["position_kill"] for floor in sham_floors) else "PASS")
        ),
    }
    surface_detection = legs.get("surface")
    gradient_detection = legs.get("gradient")
    ks = {
        "surface_detection": surface_detection,
        "gradient_detection": gradient_detection,
        "verdict": (
            "UNREADABLE"
            if surface_detection is None or gradient_detection is None
            else ("KILL" if surface_detection >= gradient_detection else "PASS")
        ),
    }
    # v0.1: per leg, each against the same registered floor. v0 pooled shams (where draws
    # SHOULD scatter on a re-shuffled shelf with nothing to find) with measurement legs
    # (where draws should agree on the target) — two tasks under one number.
    by_leg: dict[str, Any] = legs.get("kd_by_leg") or {}
    kd = {
        "floor": KD_AGREEMENT_FLOOR,
        "by_leg": by_leg,
        "verdict": {
            leg: (
                "UNREADABLE"
                if agreement is None
                else ("NOISE" if agreement < KD_AGREEMENT_FLOOR else "PASS")
            )
            for leg, agreement in by_leg.items()
        }
        or "UNREADABLE",
    }
    return {"KP": kp, "KS": ks, "KD": kd}


# ----------------------------------------------------------------------------------- selftest


def selftest() -> int:
    """The free leg: every registered definition on inputs whose answers are hand-stated."""
    failures: list[str] = []

    def _row(index: int, words: int) -> dict[str, Any]:
        listing = " ".join(f"w{index}n{token}" for token in range(words))
        return {
            "title": f"Title {index}",
            "listing": f"{listing}.",
            "followers": 1000 - index,
            "source": f"high{index}",
        }

    high = [_row(i, 40 + i) for i in range(30)]
    low = [
        {"title": f"Low {i}", "listing": " ".join(f"l{i}w{t}" for t in range(42)) + ".",
         "followers": 3, "source": f"low{i}"}
        for i in range(10)
    ]

    rendered = render_shelf(high[:SHELF_SIZE])
    numbered = [f"{n}." in rendered for n in range(1, SHELF_SIZE + 1)]
    if not all(numbered) or ASK not in rendered or SYSTEM in rendered:
        failures.append("render_shelf must number all six blocks and carry the ask")
    digests = [digest_of(page(row)) for row in high[:SHELF_SIZE]]
    if any(d in rendered for d in digests):
        failures.append("the rendering must embed no digest text")
    if len(matched_pairs(high, low, 8)) != 8:
        failures.append("matched_pairs must produce the requested count")

    first = seeded_order(high, seed_of("a"))
    again = seeded_order(high, seed_of("a"))
    other = seeded_order(high, seed_of("b"))
    if first != again or first == other:
        failures.append("the seeded shuffle must be deterministic and seed-sensitive")
    if build_sham_shelves(high, 3)[0]["members"] != build_sham_shelves(high, 3)[0]["members"]:
        failures.append("sham construction must be deterministic")

    good = parse_answer('{"off_shelf": 4, "phrase": "a patch of notes"}')
    if good is None or good["off_shelf"] != 4:
        failures.append("a well-formed answer must parse")
    bad = [
        "",
        "not json",
        '{"off_shelf": 7, "phrase": "x"}',
        '{"off_shelf": true, "phrase": "x"}',
        '{"off_shelf": 0, "phrase": "leftover"}',
        '{"off_shelf": 3, "phrase": ""}',
        '{"off_shelf": 3}',
        '{"off_shelf": 3, "phrase": "x", "rating": 5}',
    ]
    if any(parse_answer(text) is not None for text in bad):
        failures.append("every malformed shape must parse to one None")

    hand = [
        {"target_slot": 3, "named_slot": 3},
        {"target_slot": 5, "named_slot": 2},
        {"target_slot": 1, "named_slot": 0},
    ]
    got = tally_draws(hand)
    if got["hits"] != 1 or got["zeros"] != 1 or got["answered"] != 3:
        failures.append("hand-built answers must tally hit, miss and zero")
    if abs((got["detection"] or 0) - 1 / 3) > 1e-9:
        failures.append("detection must be the answered-draw share naming the target")

    sham_a = [{"named_slot": 4}, {"named_slot": 4}, {"named_slot": 0}, {"named_slot": 0}]
    sham_b = [{"named_slot": 1}, {"named_slot": 2}, {"named_slot": 0}, {"named_slot": 0}]
    floor_a, floor_b = sham_floor(sham_a), sham_floor(sham_b)
    if floor_a["false_alarm"] != 0.5 or floor_a["modal_slot"] != 4:
        failures.append("a floor must come from its own shelf's rows alone")
    if floor_b["modal_share"] != 0.5 or floor_a["modal_share"] != 1.0:
        failures.append("two shams' floors must stay two floors")

    long_text = " ".join(f"sentence number {i} keeps going." for i in range(12))
    cut = truncate_to_word_count(long_text, 10)
    if not cut.endswith(".") or len(cut.split()) > 10 or cut not in long_text:
        failures.append("the truncation must keep whole sentences under the target length")

    listing = "The wards held. His mana was a patch of notes by the third gate."
    ours = phrase_record("patch of notes", listing, is_ours=True)
    theirs = phrase_record("patch of notes", listing, is_ours=False)
    if ours.get("verbatim") != "patch of notes" or ours["token_offsets"] != [7, 10]:
        failures.append("an ours-slot phrase is stored verbatim with offsets")
    if "verbatim" in theirs or theirs["token_offsets"] != [7, 10] or not theirs["located"]:
        failures.append("a market-slot phrase row carries offsets and no text")
    if phrase_record("never present anywhere", listing, is_ours=False) != {"located": False}:
        failures.append("an unlocatable market phrase stores nothing but located False")

    table = kills(
        [floor_a],
        {"gradient": 0.8, "surface": 0.2, "kd_by_leg": {"gradient": 0.75, "sham": 0.3}},
    )
    if table["KS"]["verdict"] != "PASS" or table["KP"]["verdict"] != "KILL":
        failures.append("the kill table mis-reads a passing KS and a tracked KP")
    if table["KD"]["verdict"] != {"gradient": "PASS", "sham": "NOISE"}:
        failures.append("KD must verdict each leg against the floor, never a pooled number")

    draw_orders = [
        seeded_order(high[:SHELF_SIZE], seed_of(BLURB_SHELF_VERSION, "sham_x", "draw", d))
        for d in range(K_DRAWS)
    ]
    if len({tuple(r["source"] for r in order) for order in draw_orders}) < 2:
        failures.append("per-draw sham re-shuffles must actually vary the slot a row lands in")
    if registration_digest() != registration_digest():
        failures.append("registration digest unstable")

    for line in failures:
        print(f"FAIL {line}", file=sys.stderr)
    print("selftest: " + ("FAILED" if failures else "passed"), file=sys.stderr)
    return 1 if failures else 0


# ------------------------------------------------------------------------------------ the run


def _complete(registry: Any, rows: list[dict[str, Any]]) -> Any:
    """One shelf, one request, the measurement conventions (`blurb_perception.probe`)."""
    from litharness.domain.generation import CompletionRequest

    request = CompletionRequest(
        prompt=render_shelf(rows),
        system=SYSTEM,
        schema=ANSWER_SCHEMA,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        profile=PROFILE,
        call_class="generation",
        timeout_seconds=300.0,
    )
    result, _ = registry.complete(request)
    return result


def run(
    registry: Any, shelves: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """K draws per shelf, the target's slot rotating; records, phrase rows, compositions."""
    records: list[dict[str, Any]] = []
    phrases: list[dict[str, Any]] = []
    compositions: dict[str, Any] = {}
    for shelf in shelves:
        target = shelf["target"]
        start = target_start_slot(shelf["name"])
        every = shelf["members"] if target is None else [*shelf["fillers"], target]
        composition: dict[str, Any] = {
            "leg": shelf["leg"],
            "members": [digest_of(page(row)) for row in every],
            "start_slot": start + 1,
            "target": digest_of(page(target)) if target is not None else None,
        }
        if "truncated_to_words" in shelf:
            composition["truncated_to_words"] = shelf["truncated_to_words"]
        compositions[shelf["name"]] = composition
        for draw in range(K_DRAWS):
            slot = (start + draw) % SHELF_SIZE
            rows = (
                # Re-shuffled per draw (v0.1): on v0's static shams, a reader consistently
                # naming the same listing necessarily fixed a slot, so KP could not tell
                # identity-consistency from position bias. Now the same complaint about the
                # same listing lands on a different slot each draw, and the modal SLOT means
                # position again; the modal LISTING is reported beside it off `named_digest`.
                seeded_order(
                    shelf["members"], seed_of(BLURB_SHELF_VERSION, shelf["name"], "draw", draw)
                )
                if target is None
                else slot_placement(shelf["fillers"], target, slot)
            )
            record: dict[str, Any] = {
                "leg": shelf["leg"],
                "shelf": shelf["name"],
                "draw": draw,
                "slot": slot + 1,
                "target_slot": slot + 1 if target is not None else None,
                "named_slot": None,
            }
            try:
                result = _complete(registry, rows)
            except Exception as error:  # an outage is a fact about the day, not about the text
                record["refusal"] = str(error)[:160]
                records.append(record)
                continue
            parsed = result.parsed if isinstance(result.parsed, dict) else None
            answer = parse_answer(json.dumps(parsed)) if parsed is not None else None
            record["named_slot"] = answer["off_shelf"] if answer else None
            if answer and answer["off_shelf"]:
                record["named_digest"] = digest_of(page(rows[answer["off_shelf"] - 1]))
            records.append(record)
            if answer and answer["off_shelf"]:
                named_row = rows[answer["off_shelf"] - 1]
                phrases.append(
                    record
                    | {
                        "phrase": phrase_record(
                            answer["phrase"],
                            str(named_row["listing"]),
                            is_ours=named_row is target,
                        )
                    }
                )
    return records, phrases, compositions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", default=str(DERIVED / "rivals.json"))
    parser.add_argument("--low", default=str(DERIVED / "rivals-low.json"))
    parser.add_argument("--texts", nargs="*", default=[], help="ours, `listing_arena` shape")
    parser.add_argument("--shams", type=int, default=SHAM_SHELVES)
    parser.add_argument("--pairs", type=int, default=GRADIENT_PAIRS)
    parser.add_argument("--surface", type=int, default=SURFACE_SHELVES)
    parser.add_argument("--out", type=Path, default=RESULTS / "blurb-shelf.json")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--i-am-the-gated-run", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.run and not args.dry_run:
        parser.error("pass one of --selftest, --dry-run, --run")
    if args.run and not args.i_am_the_gated_run:
        print(
            "refusing: --run needs --i-am-the-gated-run; this spend is gated on the operator",
            file=sys.stderr,
        )
        return 1
    if args.run and not args.yes:
        print("pass --yes to spend, or --dry-run to see the plan", file=sys.stderr)
        return 1
    if not args.texts:
        parser.error("--texts is required for --dry-run and --run")

    from listing_arena import load_texts  # lazy: the free legs never import it

    texts = load_texts(args.texts)
    calls = K_DRAWS * (args.shams + args.pairs + args.surface + len(texts))
    if args.dry_run:
        print(
            f"{calls} calls exactly: K={K_DRAWS} x ({args.shams} shams "
            f"+ {args.pairs} gradient + {args.surface} surface + {len(texts)} ours)"
        )
        print("dry run: no registry constructed, nothing spent", file=sys.stderr)
        return 0

    from litharness.providers import build_default_registry  # lazy: heavy, paid path only

    high = json.loads(Path(args.pool).read_text(encoding="utf-8"))
    low = json.loads(Path(args.low).read_text(encoding="utf-8"))
    shelves = (
        build_sham_shelves(high, args.shams)
        + build_gradient_shelves(high, low, args.pairs)
        + build_ours_shelves(high, texts)
        + build_surface_shelves(high, low, args.surface)
    )
    print(
        f"{len(shelves)} shelf/shelves, {calls} calls: {args.shams} shams, "
        f"{args.pairs} gradient, {len(texts)} ours, {args.surface} surface"
    )

    records, phrases, compositions = run(build_default_registry(), shelves)

    per_shelf: dict[str, Any] = {}
    leg_agreements: dict[str, list[float]] = {}
    for shelf in shelves:
        mine = [r for r in records if r["shelf"] == shelf["name"]]
        per_shelf[shelf["name"]] = (
            sham_floor(mine) if shelf["leg"] == "sham" else tally_draws(mine)
        )
        agreement = draw_agreement([r["named_slot"] for r in mine])
        if agreement is not None:
            leg_agreements.setdefault(shelf["leg"], []).append(agreement)

    def leg_rate(leg: str) -> float | None:
        tally = tally_draws([r for r in records if r["leg"] == leg])
        return None if not tally["answered"] else tally["hits"] / tally["answered"]

    legs = {
        "gradient": leg_rate("gradient"),
        "surface": leg_rate("surface"),
        "ours": leg_rate("ours"),
        # v0.1: per leg — a sham's draws SHOULD scatter on a re-shuffled shelf while a
        # measurement leg's should agree on the target; pooling them was two tasks under one
        # number, and it is the pooled figure that read 0.476 on the first run.
        "kd_by_leg": {
            leg: statistics.fmean(values) for leg, values in sorted(leg_agreements.items())
        },
    }
    report = {
        "study": BLURB_SHELF_VERSION,
        "registration_digest": registration_digest(),
        "calls": calls,
        "shelves": compositions,
        # Per-sham floors live under per-sham keys forever; nothing here averages them.
        "per_shelf": per_shelf,
        "phrases": phrases,
        "kills": kills([per_shelf[s["name"]] for s in shelves if s["leg"] == "sham"], legs),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")

    for name, summary in per_shelf.items():
        rate = summary["false_alarm"] if "false_alarm" in summary else summary["detection"]
        print(f"  {name:28} draws {summary['draws']:3}  rate {rate}")
    table = report["kills"]
    kd_verdict = table["KD"]["verdict"]
    kd_text = (
        " ".join(f"{leg}:{verdict}" for leg, verdict in kd_verdict.items())
        if isinstance(kd_verdict, dict)
        else kd_verdict
    )
    print(f"\nKP {table['KP']['verdict']}  KS {table['KS']['verdict']}  KD {kd_text}")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
