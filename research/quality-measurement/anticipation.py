"""The anticipation probe: stop mid-chapter, describe what could happen next, mark the stance.

`plan/anticipation-probe-validity.md` is the registration; this module carries the frozen
bytes and every registered definition. The hypothesis under test: flat text yields vague,
low-specificity hypotheses with no preference over outcomes; gripping text yields sharp,
concrete predictions with a hope/dread gap. The probe lives in the report channel — the one
frame that survived every verdict death (§89's E6): the persona **describes** futures and
marks its own stance; nothing rates anything, and the schema is closed so no verdict
vocabulary can arrive.

The damage arm is the operator's named one: `ablate.destake` deletes the stakes-establishing
sentences, and it is read against `ablate.deplete_matched` or not at all — the same number of
words from zero-stake sentences, so the difference between the two rows is the entire claim
(the persona-battery rule, inherited byte for byte in spirit).

The ledger reserves its preference vocabulary (§90-§97) and none of it appears here; the
hope/dread quantity is **stance spread**.

Free legs first; the paid run is small and still refused without `--yes`:

    uv run python research/quality-measurement/anticipation.py --selftest
    uv run python research/quality-measurement/anticipation.py --dry-run
    uv run python research/quality-measurement/anticipation.py --run --yes
"""

from __future__ import annotations

import argparse
import dataclasses
import itertools
import json
import statistics
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ablate  # noqa: E402
import personas  # noqa: E402

RESULTS = HERE / "results"
SCENES = HERE / "corpora" / "toll-scenes.json"

# ---------------------------------------------------------------- the registration, frozen

ANTICIPATION_VERSION = "anticipation.v0"

#: Fraction of the passage's words behind the stop point; the boundary snaps to the nearest
#: paragraph break so the reader is never stopped mid-thought by the instrument itself.
STOP_FRACTION = 0.6

#: Draws per (passage, arm, persona) cell. The comic-beat census measured a one-draw locator
#: at 0.54 reliability; four draws is that lesson applied rather than remembered.
K_DRAWS = 4

#: Outcomes requested per draw, exactly.
N_OUTCOMES = 3

#: An outcome is scored on its first this-many words; length may not buy specificity.
OUTCOME_MAX_WORDS = 50

#: Content tokens shorter than this are dropped (possessive artifacts ground nothing).
MIN_TOKEN_LENGTH = 2

#: The arms, all `ablate` at strength 1.0, nothing invented. destake is the operator's named
#: damage arm; deplete_matched is its mandatory word-matched control; the standing sham pair
#: rides as always.
ARMS: tuple[str, ...] = (
    "original",
    "destake",
    "deplete_matched",
    "rename_entities",
    "rewhitespace",
)

#: K1's floor: the five arms' mean specificity must span at least this or the probe is a
#: constant function and nothing downstream is defined.
K1_SPAN_FLOOR = 0.05

#: K2's margin: destake's absolute distance from the original must clear the largest single
#: sham's absolute distance by this much, per sham and never pooled.
K2_MARGIN = 0.05

#: Refuse above this many calls without --yes.
CALL_GUARD = 1_000

PROBE_MAX_TOKENS = 350

#: **Byte-frozen.** Describe, never rate: no quality vocabulary, no scale, no comparison to
#: any other text. The stance question is about the reader's own pull, in behavioural words.
PROBE = (
    "You have read this far and the chapter continues below the cut. Without judging the "
    "writing in any way, describe the three most concrete things that could plausibly happen "
    "next in this story. Be specific: name the people, objects and places involved. For each, "
    "say whether you notice yourself hoping it happens, dreading it, or neither.\n\n"
    'Answer as a JSON array of exactly three objects: [{"outcome": "<one or two sentences>", '
    '"stance": "hope" | "dread" | "neither"}, ...]'
)

STANCES: tuple[str, ...] = ("hope", "dread", "neither")

PROBE_SCHEMA: dict[str, object] = {
    "type": "array",
    "minItems": N_OUTCOMES,
    "maxItems": N_OUTCOMES,
    "items": {
        "type": "object",
        "properties": {
            "outcome": {"type": "string"},
            "stance": {"enum": list(STANCES)},
        },
        "required": ["outcome", "stance"],
        "additionalProperties": False,
    },
}

#: The frozen stopword list `content_tokens` removes — registered bytes, because the
#: specificity definition is only as stable as this set. Function words only; nothing here
#: could carry story content.
_STOPWORD_TEXT = (
    "a an the and or but if then than as of to in on at by for with from into onto over "
    "under about after before between through during is are was were be been being am do "
    "does did have has had having he she it they them him her his hers its their theirs i "
    "you we us our your my me mine yours this that these those there here who whom whose "
    "which what when where why how not no nor so too very just also still even only own "
    "same such will would can could may might must shall should up down out off again "
    "further once more most some any each few both all now"
)
STOPWORDS: frozenset[str] = frozenset(_STOPWORD_TEXT.split())

PRE_REGISTRATION: dict[str, Any] = {
    "version": ANTICIPATION_VERSION,
    "stop_fraction": STOP_FRACTION,
    "k_draws": K_DRAWS,
    "n_outcomes": N_OUTCOMES,
    "outcome_max_words": OUTCOME_MAX_WORDS,
    "min_token_length": MIN_TOKEN_LENGTH,
    "arms": list(ARMS),
    "k1_span_floor": K1_SPAN_FLOOR,
    "k2_margin": K2_MARGIN,
    "call_guard": CALL_GUARD,
    "probe": PROBE,
    "probe_schema": PROBE_SCHEMA,
    "stances": list(STANCES),
    "stopwords_digest": sha256(" ".join(sorted(STOPWORDS)).encode()).hexdigest()[:16],
}


def registration_digest() -> str:
    material = json.dumps(PRE_REGISTRATION, sort_keys=True, ensure_ascii=False)
    return sha256(material.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- the stop point


def stop_point(text: str) -> str:
    """The passage-so-far: the paragraph boundary nearest STOP_FRACTION of the words.

    Deterministic, and always at least one paragraph and never the whole text (a probe after
    the final paragraph would be asking about a future the passage no longer holds); a
    single-paragraph text raises rather than probing an empty future.
    """
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) < 2:
        raise ValueError("stop_point needs at least two paragraphs to leave a future")
    total = sum(len(p.split()) for p in paragraphs)
    target = STOP_FRACTION * total
    best_index = 1
    best_gap = float("inf")
    seen = 0
    for index, paragraph in enumerate(paragraphs[:-1], start=1):
        seen += len(paragraph.split())
        gap = abs(seen - target)
        if gap < best_gap:
            best_gap = gap
            best_index = index
    return "\n\n".join(paragraphs[:best_index])


# ------------------------------------------------------------------------------- the scorers


def content_tokens(text: str) -> set[str]:
    """Casefolded, punctuation-stripped tokens; stopwords and single characters removed.

    The length floor exists for possessive artifacts: punctuation stripping turns
    "Marrow's" into "marrow" plus a stray "s", and a stray letter may not count as
    grounding.
    """
    cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text.casefold())
    return {
        token
        for token in cleaned.split()
        if len(token) >= MIN_TOKEN_LENGTH and token not in STOPWORDS
    }


def specificity(outcome: str, passage: str) -> float:
    """Grounding: the fraction of the outcome's content tokens present in the passage.

    Scored on the outcome's first OUTCOME_MAX_WORDS words so length cannot buy specificity.
    An outcome with no content tokens grounds at 0.0 — "it might happen" says nothing.
    """
    clipped = " ".join(outcome.split()[:OUTCOME_MAX_WORDS])
    tokens = content_tokens(clipped)
    if not tokens:
        return 0.0
    passage_tokens = content_tokens(passage)
    return len(tokens & passage_tokens) / len(tokens)


def _jaccard_distance(left: set[str], right: set[str]) -> float:
    union = left | right
    if not union:
        return 0.0
    return 1.0 - len(left & right) / len(union)


def distinctness(outcomes: Sequence[str]) -> float:
    """Mean pairwise Jaccard distance between the outcomes' content-token sets.

    Three near-duplicate vague guesses score low; three genuinely different futures score
    high. Fewer than two non-empty token sets is 0.0 — nothing to be distinct from.
    """
    sets = [content_tokens(" ".join(o.split()[:OUTCOME_MAX_WORDS])) for o in outcomes]
    sets = [s for s in sets if s]
    if len(sets) < 2:
        return 0.0
    pairs = list(itertools.combinations(sets, 2))
    return sum(_jaccard_distance(a, b) for a, b in pairs) / len(pairs)


def stance_stats(stances: Iterable[str]) -> dict[str, float | bool]:
    """engagement = 1 - neither share; bipolar = hope and dread both present."""
    marks = list(stances)
    if not marks:
        return {"engagement": 0.0, "bipolar": False}
    neither = sum(1 for mark in marks if mark == "neither")
    return {
        "engagement": 1.0 - neither / len(marks),
        "bipolar": ("hope" in marks) and ("dread" in marks),
    }


def parse_response(text: str) -> list[tuple[str, str]] | None:
    """Exactly N_OUTCOMES (outcome, stance) pairs, or None — one outcome, no partial credit.

    Non-JSON, wrong length, wrong keys, extra keys, or an out-of-enum stance are all the same
    None; folding a malformed answer into a distribution would score the format, not the
    anticipation.
    """
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list) or len(parsed) != N_OUTCOMES:
        return None
    out: list[tuple[str, str]] = []
    for item in parsed:
        if not isinstance(item, dict) or set(item) != {"outcome", "stance"}:
            return None
        outcome, stance = item["outcome"], item["stance"]
        if not isinstance(outcome, str) or stance not in STANCES:
            return None
        out.append((outcome, stance))
    return out


@dataclass(frozen=True, slots=True)
class CellScore:
    """One (passage, arm, persona) cell aggregated over its K draws."""

    passage_id: str
    arm: str
    persona_id: str
    draws_answered: int
    mean_specificity: float
    mean_distinctness: float
    engagement: float
    bipolar_rate: float
    recurrence: float  # exploratory: max cross-draw outcome similarity; never gated

    @property
    def scorable(self) -> bool:
        return self.draws_answered >= 2  # one draw is the 0.54-reliability trap


def cell_score(
    passage_id: str, arm: str, persona_id: str,
    passage: str, draws: Sequence[list[tuple[str, str]]],
) -> CellScore:
    """Aggregate one cell's answered draws into the registered measurables."""
    answered = [draw for draw in draws if draw]
    specs: list[float] = []
    dists: list[float] = []
    engagements: list[float] = []
    bipolars: list[bool] = []
    outcome_sets: list[set[str]] = []
    for draw in answered:
        outcomes = [outcome for outcome, _ in draw]
        stances = [stance for _, stance in draw]
        specs.append(statistics.fmean(specificity(o, passage) for o in outcomes))
        dists.append(distinctness(outcomes))
        stats = stance_stats(stances)
        engagements.append(float(stats["engagement"]))
        bipolars.append(bool(stats["bipolar"]))
        outcome_sets.extend(
            content_tokens(" ".join(o.split()[:OUTCOME_MAX_WORDS])) for o in outcomes
        )
    recurrence = 0.0
    for (i, left), (j, right) in itertools.combinations(enumerate(outcome_sets), 2):
        if i // N_OUTCOMES != j // N_OUTCOMES and left and right:  # across draws only
            union = left | right
            recurrence = max(recurrence, len(left & right) / len(union))
    return CellScore(
        passage_id=passage_id, arm=arm, persona_id=persona_id,
        draws_answered=len(answered),
        mean_specificity=statistics.fmean(specs) if specs else 0.0,
        mean_distinctness=statistics.fmean(dists) if dists else 0.0,
        engagement=statistics.fmean(engagements) if engagements else 0.0,
        bipolar_rate=(sum(bipolars) / len(bipolars)) if bipolars else 0.0,
        recurrence=recurrence,
    )


# --------------------------------------------------------------------------- kill conditions


def kills(cells: Sequence[CellScore]) -> dict[str, Any]:
    """The four registered kill conditions, assembled once, over scorable cells only.

    K1 constancy (arm span on mean specificity); K2 the per-sham floor with the +0.05 margin
    on specificity or engagement; K3 destake beyond deplete_matched on the same measurable;
    K4 draw reliability reported as within-cell vs between-passage spread. No bar over any
    rate; each verdict names its numbers.
    """
    usable = [cell for cell in cells if cell.scorable]

    def arm_mean(arm: str, field: str) -> float | None:
        values = [getattr(cell, field) for cell in usable if cell.arm == arm]
        return statistics.fmean(values) if values else None

    spec_by_arm = {arm: arm_mean(arm, "mean_specificity") for arm in ARMS}
    eng_by_arm = {arm: arm_mean(arm, "engagement") for arm in ARMS}

    known_spec = [value for value in spec_by_arm.values() if value is not None]
    k1_span = (max(known_spec) - min(known_spec)) if len(known_spec) >= 2 else None
    k1 = {
        "span": k1_span,
        "floor": K1_SPAN_FLOOR,
        "verdict": (
            "UNREADABLE" if k1_span is None
            else ("PASS" if k1_span >= K1_SPAN_FLOOR else "KILL")
        ),
    }

    def distances(field_by_arm: dict[str, float | None]) -> dict[str, float] | None:
        origin = field_by_arm["original"]
        if origin is None:
            return None
        return {
            arm: abs(value - origin)
            for arm, value in field_by_arm.items()
            if arm != "original" and value is not None
        }

    k2: dict[str, Any] = {"margin": K2_MARGIN, "verdict": "UNREADABLE"}
    k3: dict[str, Any] = {"verdict": "UNREADABLE"}
    for field_name, field_by_arm in (("specificity", spec_by_arm), ("engagement", eng_by_arm)):
        dist = distances(field_by_arm)
        if dist is None or "destake" not in dist:
            continue
        shams = {arm: dist[arm] for arm in ("rename_entities", "rewhitespace") if arm in dist}
        k2.setdefault("per_measurable", {})[field_name] = {
            "destake": dist["destake"],
            "shams": shams,
            "clears": bool(shams) and dist["destake"] >= max(shams.values()) + K2_MARGIN,
        }
        if "deplete_matched" in dist:
            k3.setdefault("per_measurable", {})[field_name] = {
                "destake": dist["destake"],
                "deplete_matched": dist["deplete_matched"],
                "beyond_control": dist["destake"] > dist["deplete_matched"],
            }
    if "per_measurable" in k2:
        k2["verdict"] = (
            "PASS" if any(row["clears"] for row in k2["per_measurable"].values()) else "KILL"
        )
    if "per_measurable" in k3:
        k3["verdict"] = (
            "PASS"
            if any(row["beyond_control"] for row in k3["per_measurable"].values())
            else "KILL"
        )

    original_cells = [cell for cell in usable if cell.arm == "original"]
    by_passage: dict[str, list[float]] = {}
    for cell in original_cells:
        by_passage.setdefault(cell.passage_id, []).append(cell.mean_specificity)
    passage_means = [statistics.fmean(values) for values in by_passage.values()]
    k4 = {
        "between_passage_sd": (
            statistics.pstdev(passage_means) if len(passage_means) >= 2 else None
        ),
        "note": (
            "within-cell spread needs per-draw records; the battery stores them and this "
            "table reports the comparison when a run exists"
        ),
        "verdict": "REPORTED",
    }
    return {"k1": k1, "k2": k2, "k3": k3, "k4": k4, "scorable_cells": len(usable)}


# ---------------------------------------------------------------------------------- selftest


def selftest() -> int:
    """The free leg: every registered definition on inputs whose answers are hand-stated."""
    failures: list[str] = []
    passage = (
        "Marrow counted the forged seals twice.\n\nThe gate inspector was due at dawn, and "
        "failure meant the debtor cells.\n\nRain moved in from the harbour."
    )
    sharp = "Marrow's forged seals fail at the gate and the inspector opens the debtor cells."
    vague = "Something unexpected might possibly occur eventually somehow."
    if not specificity(sharp, passage) > 0.5:
        failures.append("a grounded outcome must score above 0.5 specificity")
    if specificity(vague, passage) != 0.0:
        failures.append("an ungrounded outcome must score 0.0 specificity")
    if not distinctness([sharp, vague, "The rain floods the harbour road."]) > 0.5:
        failures.append("three different futures must be distinct")
    if distinctness([sharp, sharp, sharp]) != 0.0:
        failures.append("identical futures must score 0.0 distinctness")
    stats = stance_stats(["hope", "dread", "neither"])
    if abs(float(stats["engagement"]) - 2 / 3) > 1e-9 or not stats["bipolar"]:
        failures.append("stance stats mis-scored the mixed cell")
    good = json.dumps(
        [{"outcome": "x", "stance": "hope"}] * 2 + [{"outcome": "y", "stance": "neither"}]
    )
    if parse_response(good) is None or parse_response('[{"outcome": "x"}]') is not None:
        failures.append("the parser accepted or refused the wrong shape")
    two = "one paragraph here.\n\nsecond paragraph follows with more words in it."
    if stop_point(two) != "one paragraph here.":
        failures.append("stop_point must keep at least one paragraph and never the whole text")
    if registration_digest() != registration_digest():
        failures.append("registration digest unstable")
    for line in failures:
        print(f"FAIL {line}", file=sys.stderr)
    print("selftest: " + ("FAILED" if failures else "passed"), file=sys.stderr)
    return 1 if failures else 0


# --------------------------------------------------------------------------------- the driver


def _arm_text(name: str, text: str) -> str:
    if name == "original":
        return text
    transform = getattr(ablate, name)
    return transform(text, 1.0)


def load_passages(path: Path = SCENES, *, min_words: int = 500) -> list[tuple[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        (str(scene["unit_id"]), str(scene["text"]))
        for scene in payload["scenes"]
        if len(str(scene["text"]).split()) >= min_words
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--model", default="claude-haiku-4-5")
    parser.add_argument("--cache", default="anticipation-raw.jsonl")
    parser.add_argument("--out", default="anticipation.json")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    passages = load_passages()
    calls = len(passages) * len(ARMS) * len(personas.GENRE_PANEL) * K_DRAWS
    print(
        f"{len(passages)} passage(s) x {len(ARMS)} arm(s) x "
        f"{len(personas.GENRE_PANEL)} persona(s) x {K_DRAWS} draw(s) = {calls} call(s)"
    )
    if args.dry_run:
        for passage_id, text in passages:
            for arm in ARMS:
                transformed = _arm_text(arm, text)
                shown = stop_point(transformed)
                print(
                    f"  {passage_id:14s} {arm:16s} stop at {len(shown.split())} of "
                    f"{len(transformed.split())} words"
                )
        print("dry run: no elicitor constructed, nothing spent", file=sys.stderr)
        return 0
    if not args.run:
        parser.error("pass one of --selftest, --dry-run, --run")
    if calls > CALL_GUARD and not args.yes:
        print(f"{calls} calls exceeds the {CALL_GUARD} guard; pass --yes", file=sys.stderr)
        return 1
    if not args.yes:
        print("pass --yes to spend, or --dry-run to see the plan", file=sys.stderr)
        return 1

    from elicit import Elicitor  # imported here so the free legs never touch it

    cells: list[dict[str, Any]] = []
    with Elicitor(Path(args.cache), model=args.model, spot_model=None) as elicitor:
        for passage_id, text in passages:
            for arm in ARMS:
                transformed = _arm_text(arm, text)
                shown = stop_point(transformed)
                for persona in personas.GENRE_PANEL:
                    draws: list[list[tuple[str, str]] | None] = []
                    for draw in range(K_DRAWS):
                        record = elicitor.ask_raw(
                            personas.system_prompt(persona),
                            [{"role": "user", "content": shown + "\n\n---\n\n" + PROBE}],
                            schema=PROBE_SCHEMA,
                            max_tokens=PROBE_MAX_TOKENS,
                            tag={
                                "study": ANTICIPATION_VERSION, "passage": passage_id,
                                "arm": arm, "persona": persona.persona_id, "draw": draw,
                            },
                            sample=draw,
                            model=args.model,
                        )
                        draws.append(parse_response(record.get("text") or ""))
                    score = cell_score(
                        passage_id, arm, persona.persona_id, shown,
                        [d for d in draws if d is not None],
                    )
                    cells.append(
                        {
                            "score": dataclasses.asdict(score),
                            "raw_draws": [
                                [list(pair) for pair in d] if d else None for d in draws
                            ],
                        }
                    )
        spend = elicitor.spend()

    scored = [
        CellScore(**{
            key: cell["score"][key]
            for key in (
                "passage_id", "arm", "persona_id", "draws_answered", "mean_specificity",
                "mean_distinctness", "engagement", "bipolar_rate", "recurrence",
            )
        })
        for cell in cells
    ]
    result = {
        "study": ANTICIPATION_VERSION,
        "registration": PRE_REGISTRATION,
        "registration_digest": registration_digest(),
        "model": args.model,
        "spend": spend,
        "cells": cells,
        "kills": kills(scored),
    }
    out = RESULTS / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
    print(f"wrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
