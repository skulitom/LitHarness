"""Track E: where, between representation and verdict, does discrimination die?

§87 left a shape rather than an answer. On `interiority_strip_matched` a mean-pooled readout of
the model's own representation of the prose ordered **9 of 9** scenes, the readout taken at the
position a verdict is generated from ordered **5 of 9**, and the panel that was actually asked
read 0.3889 with an interval spanning indifference. Every instrument that answers a slot failed;
every instrument that measured without being asked succeeded. That is a report deficit, and this
module asks the question it implies: **is the loss in the asking, and is any way of asking
lossless?**

**The counter-decidable families are what make the question answerable.** On B6 (§88) a quantity
named before any result was read orders every decidable pair — `system_digit_count`,
`interior_per_1k`, `em_per_1k`. So for the first time there is ground truth about whether a
difference is *present*, independent of any instrument's opinion, and a protocol can be scored on
whether its channel carries a difference known to be there.

**What a protocol clearing here does and does not mean.** It means the difference survived to
that protocol's output. It does not mean the difference matters to a reader: §82 governs verbatim,
`domain/calibration.py` defines PREFERENCE as a human's blinded choice, and B6's counter is a
discrimination oracle rather than a taste. A protocol that clears B6 becomes a candidate for
JudgeBench A2's verdict layer; it does not become a judge of quality.

Six protocols, two mandatory controls, one positive control, and a statistic declared with its
own attainable floor beside it — the failure this project has recorded three times (§81's point
estimate, §85's zero-width band, §87's sign-flip floor) is a bar written in a form its design
could never reach.

Runs under `uv run python`. `--transport cli` spends against the local install's subscription;
`spend()` reports the equivalent price. E3 is not here — it needs logits and therefore torch, and
it lives in `verdict_locus.py` under the MirrorBench interpreter.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from collections.abc import Sequence
from math import comb
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from b6_benchmark import (  # noqa: E402
    CONTROLS,
    MEMBERS,
    POSITIVE_CONTROL,
    admitted_families,
    control_families,
    decidable,
)
from elicit import Comparison, Elicitor, positional_bias  # noqa: E402
from latent_fixtures import Pair, clopper_pearson  # noqa: E402
from personas import PAIR_QUESTION, PAIR_SCHEMA, PANEL, REASON_CODES, Persona  # noqa: E402

RESULTS = HERE / "results"

#: The band a judge's chose-A rate must sit inside before any preference it reports is read.
#: §69's check; `latent_crossfamily.BIAS_BAND` uses the same numbers and this restates them
#: rather than importing, because that module screens *candidates* and this one screens
#: *protocols* — a shared constant would imply the two thresholds move together.
BIAS_BAND = (0.40, 0.60)

#: §86.7's floor. A rate on fewer decided comparisons than this is not read as a band at all.
#: §87.3 is why the number is here: `gemma3:4b` was disqualified on a chose-A rate of 1.000 that
#: rested on **eleven** decisions, and the entry had to say so in the same breath as the number.
DECIDED_FLOOR = 30

#: Per-family significance. Not Bonferroni-corrected, because the protocol-level rule below is
#: itself the multiplicity control: requiring two of three families to clear at 0.05 puts the
#: protocol's family-wise error at 3(0.05^2)(0.95) + 0.05^3 = 0.0072 under a global null.
FAMILY_ALPHA = 0.05

#: How many of B6's three families a protocol must clear to survive. The directive's condition.
FAMILIES_TO_SURVIVE = 2


# --------------------------------------------------------------------------- the statistic

def exact_two_sided(k: int, groups: int) -> float:
    """Two-sided exact binomial p at p = 1/2, by enumeration over all `2**groups` labellings."""
    if groups <= 0:
        return 1.0
    tail = min(k, groups - k)
    weight = sum(comb(groups, i) for i in range(tail + 1))
    return min(1.0, 2.0 * weight / 2**groups)


def attainable_p(groups: int) -> float:
    """The smallest p this statistic can produce at `groups` pairs: `2 / 2**groups`."""
    return exact_two_sided(groups, groups)


def required_k(groups: int, alpha: float = FAMILY_ALPHA) -> int | None:
    """Fewest aligned pairs that clear `alpha`, or None when no count can. Declared, then used."""
    for k in range(groups // 2 + 1, groups + 1):
        if exact_two_sided(k, groups) <= alpha:
            return k
    return None


def fisher_exact_greater(a: int, b: int, c: int, d: int) -> float:
    """One-sided Fisher exact p for `a/(a+b)` exceeding `c/(c+d)`. E6's null, which is measured.

    E6 is scored by a matcher rather than by a choice, so its chance rate is not 1/2 and cannot be
    assumed: a matcher for "did it name the numbers" fires at whatever rate that vocabulary shows
    up unprompted. The rate is therefore **estimated from the same run**, on the families whose
    transform is not that axis, and the comparison is a 2x2 exact test rather than a binomial
    against a number somebody chose.
    """
    total = a + b + c + d
    if total == 0 or (a + b) == 0 or (c + d) == 0:
        return 1.0
    row, col = a + b, a + c
    return min(1.0, sum(
        comb(row, i) * comb(total - row, col - i) / comb(total, col)
        for i in range(a, min(row, col) + 1)
    ))


# --------------------------------------------------------------------------- E6's matchers

#: The axis matcher for each family, **committed before any E6 response exists**. The matcher is
#: the rubric: E6 asks a model to name the most salient difference and is scored on whether it
#: named the axis the transform is defined in terms of, so a matcher edited after reading
#: responses would be a rubric fitted to its own answers. No post-hoc leniency, in either
#: direction — a response that gestures at the right thing in words the matcher misses is a miss.
#:
#: They are deliberately generous about vocabulary and strict about topic. A model that says
#: "the numbers in the status block are gone" and one that says "B has no quantities" should both
#: count, because what is under test is whether the axis reached the output at all, not whether
#: the model shares our terminology.
AXIS_MATCHERS: dict[str, str] = {
    "stat_flatten": (
        r"\b(number|numeric|numeral|digit|figure|quantit|stat|stats|statistic|status|value|"
        r"score|count|percent|damage|hp\b|mp\b|xp\b|level|tier|metric|readout|specific)\w*"
    ),
    "interiority_strip_matched": (
        r"\b(interior|inner|internal|introspect|thought|thinking|feel|feeling|felt|emotion|"
        r"reflect|reaction|psycholog|mind|mental|consciousness|subjectiv|perspective|"
        r"first[- ]person|access to)\w*"
    ),
    "repair_emdash": (
        r"(\bem[- ]?dash|\bdash(es)?\b|\bpunctuat|\bhyphen|\bcomma|\bsentence structure|"
        r"\bclause|—)"
    ),
}


def axis_named(family: str, text: str) -> bool:
    """Did this response name `family`'s axis? Deterministic, and the matcher is frozen above."""
    pattern = AXIS_MATCHERS.get(family)
    return bool(pattern) and re.search(pattern, text, flags=re.IGNORECASE) is not None


# --------------------------------------------------------------------------- the protocols

#: The rating scale E4 asks for. Wide on purpose: gate 0 measured the three-way absolute verdict
#: returning `keep-reading` on 195 of 196 draws — a constant function with every variance
#: statistic undefined — and a 0-10 scale has enough ties in it to repeat that. If E4 collapses
#: anyway, that is E4's finding and the width is what makes it a finding rather than a floor
#: effect we built.
E4_SCALE = 100

E4_QUESTION = (
    "One passage. How strongly did it make you want to keep reading — a whole number from 0 to "
    f"{E4_SCALE}, where 0 is 'I would put this down' and {E4_SCALE} is 'I would not stop'.\n\n"
    "Answer for this passage on its own. Nothing is being compared."
)

E4_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {"rating": {"type": "integer", "minimum": 0, "maximum": E4_SCALE}},
    "required": ["rating"],
    "additionalProperties": False,
}

#: E5's first turn. `pair_turn`'s docstring warns that a near-identical pair invites diff-spotting
#: — an editing frame, which is the §1a.2 question this programme exists to avoid — so stage 1
#: asks for each passage **in turn** and never for a comparison. The word "difference" does not
#: appear, and neither does "compare": stage 2 does the choosing, and a stage 1 that pre-empted it
#: would be E6 wearing E5's name.
E5_STAGE1 = (
    "Two passages, one after the other. Before choosing anything: for each in turn, say what "
    "reading it was like — what you noticed and what it did to you. Two or three sentences each."
)

#: E6's turn, and it is the one place the diff-spotting frame is deliberate. E6 is not a
#: preference protocol: it asks whether the model can *articulate* the axis, independent of
#: preferring anything, which is the purest test of the report channel this study has.
E6_QUESTION = (
    "Two passages. Name the single most salient difference between them, in one sentence.\n\n"
    "Describe what the difference is, not which passage you prefer."
)

E6_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {"difference": {"type": "string"}},
    "required": ["difference"],
    "additionalProperties": False,
}

#: E5's second turn, which is `PAIR_QUESTION` **byte-for-byte** after its reason codes are
#: rendered. That is the whole design of E5: the choice put to the model is E1's choice, and the
#: only thing that differs is that a description of both passages now sits in the context above
#: it. A reworded stage 2 would confound the staging with the wording and answer neither question.
E5_STAGE2 = PAIR_QUESTION.format(
    codes=", ".join(f"`{code}`" for code in REASON_CODES if code != "none")
)

#: One JSON object out; the passages are input. Same value `elicit.PAIR_MAX_TOKENS` uses, restated
#: because E4's and E6's answers are not pair answers and should not silently follow that constant
#: if it moves for a reason that belongs to pairwise judging.
ANSWER_MAX_TOKENS = 160
E5_STAGE1_MAX_TOKENS = 400


PRE_REGISTRATION: dict[str, Any] = {
    "written": "2026-08-19, before the first elicitation of any protocol in this module",
    "question": (
        "Where between representation and verdict does discrimination die, and is any elicitation "
        "protocol lossless? Scored on B6 (§88), whose counter is ground truth for a difference "
        "being present."
    ),
    "unit_of_analysis": (
        "The pair. Personas and orientations within a pair are repeated measures on the same "
        "scene, not independent draws, and pooling them would inflate every p-value by the "
        "replication factor. A pair's score is the mean over its non-refused comparisons with a "
        "tie at 0.5; its sign is that mean against 0.5; a mean of exactly 0.5 is undecided and "
        "leaves the denominator."
    ),
    "statistic": (
        "Per family, a two-sided exact binomial sign test at p=1/2 over decided pairs, "
        "enumerated rather than approximated."
    ),
    "why_two_sided": (
        "The directive inherited §87's `2/2**G` floor with §87's reason — invariance under a "
        "global sign flip of a *fitted* direction. That reason does not transfer: B6's counters "
        "are named a priori and nothing is fitted here, so no sign-flip twin exists and the "
        "one-sided floor would be `1/2**G`. The floor is nonetheless `2/2**G`, for a stronger "
        "reason: the alternative is non-directional. B6 certifies that a difference is present, "
        "never which side of it is better, and craft doctrine ('told feeling is worse', 'em "
        "dashes are a tell') is the hypothesis under test in §87.1/§87.3 rather than a valence "
        "this study may assume. A protocol that consistently prefers *either* side has registered "
        "the difference. Choosing the one-sided test would have been choosing the more permissive "
        "statistic after seeing which way §81's rates pointed, which is what §81 refused to do."
    ),
    "family_alpha": FAMILY_ALPHA,
    "families_to_survive": FAMILIES_TO_SURVIVE,
    "protocol_level_error": (
        "Requiring 2 of 3 families at 0.05 gives 3(0.05^2)(0.95) + 0.05^3 = 0.0072 under a global "
        "null, so no further correction is applied and the per-family alpha stays attainable."
    ),
    "minimum_groups": 6,
    "bar_attainability": (
        "Declared before the run, per §87's rule. At G pairs the smallest p this statistic can "
        "produce is 2/2**G, so alpha 0.05 is unreachable below G=6. B6's three families give "
        "G=10, 9 and 7 decidable pairs, needing k=9, 8 and 7 aligned pairs respectively. "
        "`repair_emdash` at G=7 has a floor of 0.0156 and therefore clears **only** on a perfect "
        "7 of 7; that is attainable and it has no margin, and it is stated here rather than "
        "discovered afterwards."
    ),
    "power_and_the_tie_risk": (
        "Declared before the run because it is a property of the design, not of the answers. A "
        "pair's sign comes from four comparisons (two personas x two orientations), so an exact "
        "2-2 split is a tie and the pair leaves the denominator. Under a null that happens at "
        "C(4,2)/2^4 = 0.375, and §81 measured `stat_flatten` at 0.5437 — near-perfect "
        "indifference — so ties are *expected* to be common on the family this study most wants "
        "to read. A family that falls below G=6 therefore reports NOT_ATTAINABLE, which is a "
        "different outcome from FAILS and will not be converted into one: the first says the "
        "protocol could not decide enough pairs to be tested, the second says it decided them "
        "and got them wrong. §87.3's `NOT_SCREENABLE` is the same distinction, and this one is "
        "declared in advance rather than after a candidate needed it. E4 is exempt by "
        "construction — its sign is a paired difference of means, which ties only on exact "
        "cancellation."
    ),
    "e6_is_scored_differently_and_here_is_why": (
        "Every other protocol's alternative is non-directional, so a two-sided sign test is "
        "right. E6's is not: only *firing* is evidence that the axis reached the output, and a "
        "matcher that never fires would read k=G under the shared machinery and print CLEARS. So "
        "E6 uses a one-sided Fisher exact against a rate measured on the other families, its "
        "controls are read as confabulation and layout-naming rates rather than as separations, "
        "and none of its numbers enter the shared sign-test table."
    ),
    "controls": {
        "placebo_identical": (
            "Both sides are the same string. Any protocol that separates it is separating "
            "nothing, and every reading of that protocol above this line is VOID rather than "
            "weakened."
        ),
        "rewhitespace_sham": (
            "Formatting only. A protocol that recovers discrimination here is reading layout "
            "(§78.1), and that reading is VOID. Registered as a control and not as a floor, "
            "which is §87's own correction to itself."
        ),
    },
    "positive_control": (
        "`repair_interiority`, which three judge families read at 0.9509 / 1.0000 / 0.9688 "
        "(§85, §85.1, §87.3). Read as a preference and never as a counter alignment — §88 "
        "measured `interior_per_1k` moving the wrong way on `gen:scene-5` because the repair "
        "lengthens the text. Preservation is the Clopper-Pearson lower bound on the pair-level "
        "rate sitting clear of 0.50; the comparison-level win rate prints beside it because that "
        "is the quantity §85's 0.9509 is denominated in."
    ),
    "positional_precondition": (
        "E1, E2, E5 and E6 present two passages in a slot and are read only if the chose-A rate "
        "sits inside (0.40, 0.60) on at least 30 decided comparisons (§86.7). E4 shows one "
        "passage at a time and has no slot to prefer; its entry says NO_SLOT rather than "
        "reporting a precondition it cannot fail, which would be a vacuous pass."
    ),
    "e2_is_a_re_read_and_not_a_re_buy": (
        "`PAIR_QUESTION` already licenses a tie ('or neither if you truly cannot separate them'), "
        "so E1 and E2 differ in how a tie is *scored*, not in what is asked: E1 scores `neither` "
        "as half a win, E2 drops ties and reads the decided rate with the tie rate beside it as "
        "the calibration. E2 therefore re-reads E1's records and buys nothing (rail 6). What this "
        "does not test is a differently *worded* tie licence, and that stays open rather than "
        "being claimed. The finding E2 can produce is sharp regardless: if E2 clears where E1 "
        "does not, the discrimination survived the asking and died in the tie collapse."
    ),
    "e6_null": (
        "E6 is scored by a frozen matcher, so its chance rate is whatever that vocabulary's "
        "unprompted rate is and cannot be assumed to be 1/2. The null is measured in the same "
        "run: each axis matcher is applied to every family's responses, and the test is a "
        "one-sided Fisher exact on the 2x2 of (fires on its own family) against (fires on the "
        "others). `placebo_identical`'s rate is reported separately as the confabulation rate — "
        "there is no difference there to name."
    ),
    "no_inherited_figures": (
        "§79.1's rule. Every bias rate, win rate and tie rate reported here is measured on these "
        "pairs by these protocols. Nothing is carried over from §81, §85 or §87.3; those entries "
        "are cited for what they measured, never used as a value here."
    ),
    "both_readings_print": (
        "Rail 5. Every family prints its as-registered reading and its corrected reading, and no "
        "protocol retro-passes on a rule rewritten after its numbers arrived."
    ),
}


# --------------------------------------------------------------------------- pair scoring

def pair_score(scores: Sequence[float]) -> float | None:
    """One pair's score from its comparisons. `None` when nothing was scoreable."""
    return statistics.fmean(scores) if scores else None


def sign_of(score: float | None) -> int:
    """+1 above indifference, -1 below, 0 at it or absent. A 0 leaves the denominator."""
    if score is None or score == 0.5:
        return 0
    return 1 if score > 0.5 else -1


def family_reading(family: str, signs: dict[str, int], *, alpha: float = FAMILY_ALPHA) -> dict:
    """One family's verdict, with its attainable floor printed beside the p it achieved."""
    decided_scenes = [scene for scene, sign in signs.items() if sign != 0]
    groups = len(decided_scenes)
    positives = sum(1 for scene in decided_scenes if signs[scene] > 0)
    k = max(positives, groups - positives)
    floor = attainable_p(groups)
    needed = required_k(groups, alpha)
    p = exact_two_sided(k, groups)
    if groups < PRE_REGISTRATION["minimum_groups"] or needed is None:
        verdict = "NOT_ATTAINABLE"
    elif p <= alpha:
        verdict = "CLEARS"
    else:
        verdict = "FAILS"
    return {
        "family": family,
        "decided_pairs": groups,
        "undecided_pairs": sorted(scene for scene, sign in signs.items() if sign == 0),
        "aligned": k,
        "direction": "positive_side" if positives >= groups - positives else "negative_side",
        "p_two_sided": round(p, 6),
        "attainable_floor": round(floor, 6),
        "k_required": needed,
        "alpha": alpha,
        "verdict": verdict,
    }


def bias_reading(comparisons: list[Any], *, has_slot: bool) -> dict[str, Any]:
    """The positional precondition, with §86.7's floor enforced rather than mentioned."""
    if not has_slot:
        return {"precondition": "NO_SLOT",
                "note": "one passage per call; there is no position to prefer"}
    bias = positional_bias(comparisons)
    decided = int(bias.get("decided", 0) or 0)
    rate = bias.get("chose_A_rate")
    numeric = isinstance(rate, float) and rate == rate
    if decided < DECIDED_FLOOR:
        precondition = "INSUFFICIENT_DECIDED"
    elif numeric and BIAS_BAND[0] <= float(rate) <= BIAS_BAND[1]:
        precondition = "IN_BAND"
    else:
        precondition = "OUT_OF_BAND"
    return {"precondition": precondition, "decided_floor": DECIDED_FLOOR, **bias}


# --------------------------------------------------------------------------- the runners

def _fixtures(include_controls: bool = True) -> dict[str, list[Pair]]:
    """B6's admitted members, then the controls. Order is the reading order of the report."""
    families = dict(admitted_families())
    if include_controls:
        families.update(control_families())
    return families


def _progress(protocol: str, family: str, done: int, total: int) -> None:
    print(f"  {protocol} {family}: {done}/{total} pairs", file=sys.stderr, flush=True)


def _parsed(record: dict[str, Any], field: str) -> Any:
    """One field out of a schema-shaped answer, or None. A malformed answer is a refusal."""
    if record.get("refused") or not record.get("text"):
        return None
    try:
        return json.loads(record["text"]).get(field)
    except (json.JSONDecodeError, AttributeError, TypeError):
        return None


def run_pairwise(
    elicitor: Elicitor, families: dict[str, list[Pair]], personas: tuple[Persona, ...]
) -> dict[str, dict[str, list[Any]]]:
    """E1's elicitation. Both orientations, every persona, one blinded choice each.

    E2 reads these same records; see `PRE_REGISTRATION["e2_is_a_re_read_and_not_a_re_buy"]`.
    """
    out: dict[str, dict[str, list[Any]]] = {}
    for family, pairs in families.items():
        out[family] = {}
        for index, pair in enumerate(pairs, start=1):
            out[family][pair.scene] = elicitor.compare_pair(
                f"{pair.scene}|{family}", pair.negative, pair.positive, n=1, personas=personas,
            )
            _progress("E1", family, index, len(pairs))
    return out


def run_scalar(
    elicitor: Elicitor, families: dict[str, list[Pair]], personas: tuple[Persona, ...]
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """E4's elicitation: each side rated alone, with no pair anywhere in the prompt."""
    out: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for family, pairs in families.items():
        out[family] = {}
        for index, pair in enumerate(pairs, start=1):
            rows: list[dict[str, Any]] = []
            for persona in personas:
                for side, text in (("negative", pair.negative), ("positive", pair.positive)):
                    record = elicitor.ask(
                        persona,
                        [{"role": "user", "content": f"{text}\n\n---\n\n{E4_QUESTION}"}],
                        schema=E4_SCHEMA, max_tokens=ANSWER_MAX_TOKENS,
                        tag={"passage": f"{pair.scene}|{family}|{side}",
                             "persona": persona.persona_id, "stage": "scalar", "side": side},
                    )
                    rating = _parsed(record, "rating")
                    rows.append({
                        "persona": persona.persona_id, "side": side,
                        "rating": int(rating) if isinstance(rating, int | float) else None,
                    })
            out[family][pair.scene] = rows
            _progress("E4", family, index, len(pairs))
    return out


def run_two_stage(
    elicitor: Elicitor, families: dict[str, list[Pair]], personas: tuple[Persona, ...]
) -> dict[str, dict[str, list[Any]]]:
    """E5's elicitation: describe each passage in turn, then choose. Two calls per comparison."""
    out: dict[str, dict[str, list[Any]]] = {}
    for family, pairs in families.items():
        out[family] = {}
        for index, pair in enumerate(pairs, start=1):
            made: list[Any] = []
            for persona in personas:
                for orientation in (0, 1):
                    first, second = ((pair.negative, pair.positive) if orientation == 0
                                     else (pair.positive, pair.negative))
                    shown = f"PASSAGE A\n\n{first}\n\n---\n\nPASSAGE B\n\n{second}"
                    tag = {"passage": f"{pair.scene}|{family}", "persona": persona.persona_id,
                           "orientation": orientation}
                    stage1 = elicitor.ask(
                        persona, [{"role": "user", "content": f"{shown}\n\n---\n\n{E5_STAGE1}"}],
                        schema=None, max_tokens=E5_STAGE1_MAX_TOKENS,
                        tag={**tag, "stage": "describe"},
                    )
                    choice = reason = None
                    if not stage1.get("refused"):
                        stage2 = elicitor.ask(
                            persona,
                            [{"role": "user", "content": f"{shown}\n\n---\n\n{E5_STAGE1}"},
                             {"role": "assistant", "content": stage1.get("text", "")},
                             {"role": "user", "content": E5_STAGE2}],
                            schema=PAIR_SCHEMA, max_tokens=ANSWER_MAX_TOKENS,
                            tag={**tag, "stage": "judge"},
                        )
                        choice = _parsed(stage2, "choice")
                        reason = _parsed(stage2, "reason_code")
                    if choice not in ("A", "B", "neither"):
                        choice = reason = None
                    made.append(Comparison(
                        pair_id=f"{pair.scene}|{family}", persona_id=persona.persona_id,
                        sample=0, model=elicitor.model, orientation=orientation,
                        choice=choice, reason_code=reason, refused=choice is None, usage={},
                    ))
            out[family][pair.scene] = made
            _progress("E5", family, index, len(pairs))
    return out


def run_verbalize(
    elicitor: Elicitor, families: dict[str, list[Pair]], personas: tuple[Persona, ...]
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """E6's elicitation: name the difference. No choice is asked for and none is scored."""
    out: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for family, pairs in families.items():
        out[family] = {}
        for index, pair in enumerate(pairs, start=1):
            rows: list[dict[str, Any]] = []
            for persona in personas:
                for orientation in (0, 1):
                    first, second = ((pair.negative, pair.positive) if orientation == 0
                                     else (pair.positive, pair.negative))
                    record = elicitor.ask(
                        persona,
                        [{"role": "user",
                          "content": f"PASSAGE A\n\n{first}\n\n---\n\nPASSAGE B\n\n{second}"
                                     f"\n\n---\n\n{E6_QUESTION}"}],
                        schema=E6_SCHEMA, max_tokens=ANSWER_MAX_TOKENS,
                        tag={"passage": f"{pair.scene}|{family}", "persona": persona.persona_id,
                             "stage": "verbalize", "orientation": orientation},
                    )
                    said = _parsed(record, "difference")
                    rows.append({"persona": persona.persona_id, "orientation": orientation,
                                 "said": str(said) if said else "", "refused": not said})
            out[family][pair.scene] = rows
            _progress("E6", family, index, len(pairs))
    return out


# --------------------------------------------------------------------------- the scorers

def score_choices(
    elicited: dict[str, dict[str, list[Any]]], *, tie_policy: str
) -> tuple[dict[str, dict[str, int]], dict[str, Any]]:
    """Pair signs from blinded choices, under a declared tie policy. E1, E2 and E5 all land here.

    `half_win` scores `neither` as half a win and is E1's incumbent reading. `drop` removes ties
    from the denominator and is E2's: the decided rate, read as calibrated indifference, with the
    tie rate reported beside it as the calibration rather than folded into the estimate.
    """
    signs: dict[str, dict[str, int]] = {}
    ties = decided = refused = 0
    for family, by_scene in elicited.items():
        signs[family] = {}
        for scene, comparisons in by_scene.items():
            scores = []
            for comparison in comparisons:
                if comparison.refused:
                    refused += 1
                    continue
                if comparison.choice == "neither":
                    ties += 1
                    if tie_policy == "drop":
                        continue
                    scores.append(0.5)
                else:
                    decided += 1
                    scores.append(1.0 if comparison.chose_variant else 0.0)
            signs[family][scene] = sign_of(pair_score(scores))
    total = ties + decided + refused
    return signs, {
        "tie_policy": tie_policy,
        "comparisons": total,
        "decided": decided,
        "ties": ties,
        "refused": refused,
        "tie_rate": round(ties / (ties + decided), 4) if (ties + decided) else None,
    }


def score_scalar(
    elicited: dict[str, dict[str, list[dict[str, Any]]]]
) -> tuple[dict[str, dict[str, int]], dict[str, Any]]:
    """E4's pair signs, plus the magnitude the sign throws away. Both readings, per rail 5.

    The sign comes from the per-persona paired difference — each persona is one paired
    observation on the scene, so a persona rating both sides equally is a tie at 0.5 — which
    keeps E4 on the same 0.5-centred machinery as every other protocol. The mean rating
    difference is reported beside it because a protocol can be systematically ordered and
    numerically flat, and that combination is a finding rather than a wash.
    """
    signs: dict[str, dict[str, int]] = {}
    magnitudes: dict[str, float] = {}
    votes: dict[str, float] = {}
    flat = graded = 0
    for family, by_scene in elicited.items():
        signs[family] = {}
        deltas: list[float] = []
        agreeing: list[float] = []
        for scene, rows in by_scene.items():
            per_persona: list[float] = []
            scene_deltas: list[float] = []
            for persona in sorted({row["persona"] for row in rows}):
                mine = {row["side"]: row["rating"] for row in rows if row["persona"] == persona}
                low, high = mine.get("negative"), mine.get("positive")
                if low is None or high is None:
                    continue
                scene_deltas.append(float(high - low))
                if high == low:
                    flat += 1
                    per_persona.append(0.5)
                else:
                    graded += 1
                    per_persona.append(1.0 if high > low else 0.0)
            deltas.extend(scene_deltas)
            agreeing.extend(per_persona)
            # **The sign is the paired difference of means, not the persona vote.** The directive
            # says so, and the dry run showed why it matters: with two personas a vote can only
            # land on {0, 0.5, 1}, so a scene where the personas disagree is an exact tie and
            # leaves the denominator. At the tie rate a null produces that costs half the pairs
            # and drops G below the attainability floor — a design that reports NOT_ATTAINABLE
            # because of its own arithmetic rather than because of the model. A mean of signed
            # differences ties only when the differences cancel exactly.
            mean_delta = statistics.fmean(scene_deltas) if scene_deltas else None
            signs[family][scene] = (
                0 if mean_delta is None else 0 if mean_delta == 0
                else (1 if mean_delta > 0 else -1)
            )
        magnitudes[family] = round(statistics.fmean(deltas), 3) if deltas else 0.0
        votes[family] = round(statistics.fmean(agreeing), 4) if agreeing else 0.0
    return signs, {
        "mean_rating_difference": magnitudes,
        "persona_vote_rate": votes,
        "scale": E4_SCALE,
        "flat_observations": flat,
        "graded_observations": graded,
        "flat_rate": round(flat / (flat + graded), 4) if (flat + graded) else None,
        "note": (
            "a flat rate near 1.0 is gate 0's constant function returning on a wider scale. "
            "`mean_rating_difference` is the magnitude the sign discards and prints beside it "
            "(rail 5): a protocol can be systematically ordered and numerically flat, and that "
            "combination is a finding rather than a wash"
        ),
    }


def score_verbalize(
    elicited: dict[str, dict[str, list[dict[str, Any]]]]
) -> dict[str, Any]:
    """E6, scored by the frozen matchers, against a null measured in the same run.

    Every axis matcher is run against every family's responses. The diagonal is what the protocol
    is credited with; the off-diagonal is the rate at which that vocabulary appears when its axis
    is *not* what changed, which is E6's chance rate and is not 1/2. `placebo_identical` gets its
    own row: both sides are the same string, so anything named there is confabulation.
    """
    matrix: dict[str, dict[str, dict[str, int]]] = {}
    for axis in AXIS_MATCHERS:
        matrix[axis] = {}
        for family, by_scene in elicited.items():
            fired = seen = 0
            for rows in by_scene.values():
                for row in rows:
                    if row["refused"]:
                        continue
                    seen += 1
                    fired += axis_named(axis, row["said"])
            matrix[axis][family] = {"fired": fired, "responses": seen}
    readings = {}
    for axis in AXIS_MATCHERS:
        own = matrix[axis][axis]
        others = [row for family, row in matrix[axis].items()
                  if family != axis and family != "placebo_identical"]
        off_fired = sum(row["fired"] for row in others)
        off_seen = sum(row["responses"] for row in others)
        placebo = matrix[axis].get("placebo_identical", {"fired": 0, "responses": 0})
        readings[axis] = {
            "own_rate": round(own["fired"] / own["responses"], 4) if own["responses"] else None,
            "null_rate": round(off_fired / off_seen, 4) if off_seen else None,
            "confabulation_rate": (
                round(placebo["fired"] / placebo["responses"], 4)
                if placebo["responses"] else None
            ),
            "fisher_p": round(fisher_exact_greater(
                own["fired"], own["responses"] - own["fired"],
                off_fired, off_seen - off_fired), 6),
            "verdict": "NAMES_THE_AXIS" if fisher_exact_greater(
                own["fired"], own["responses"] - own["fired"],
                off_fired, off_seen - off_fired) <= FAMILY_ALPHA else "DOES_NOT",
        }
    return {"confusion": matrix, "readings": readings}


def verbalize_rows(
    elicited: dict[str, dict[str, list[dict[str, Any]]]], scored: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """E6's member and control rows, decided by the Fisher test rather than by a sign test.

    **The sign test is wrong for E6 and the dry run is what showed it.** Scoring a pair by
    whether its matcher fired and then testing that count two-sided rewards *consistent silence*
    exactly as much as consistent naming: a matcher that never fires reads `k = G` and prints
    CLEARS. That is correct for every other protocol here, where preferring either side registers
    the difference, and nonsense for this one, where only firing is evidence. So E6's direction is
    not arbitrary, its null is not 1/2, and its verdict comes from the one-sided Fisher test
    against a rate measured in the same run.

    The controls read in E6's own currency too. `placebo_identical` is the confabulation check —
    both sides are the same string, so any axis named there was invented — and `rewhitespace_sham`
    sits inside the null pool, since a matcher firing on a formatting-only pair is precisely the
    layout reading §78.1 refuses. A control "separates" when the matcher fires on it at or above
    the rate it fires on its own family.
    """
    members: list[dict[str, Any]] = []
    for family in MEMBERS:
        reading = scored["readings"][family]
        cell = scored["confusion"][family][family]
        members.append({
            "family": family,
            "aligned": cell["fired"],
            "decided_pairs": cell["responses"],
            "own_rate": reading["own_rate"],
            "null_rate": reading["null_rate"],
            "p_two_sided": reading["fisher_p"],
            "attainable_floor": None,
            "k_required": None,
            "statistic": "one-sided Fisher exact against a null measured on the other families",
            "verdict": "CLEARS" if reading["verdict"] == "NAMES_THE_AXIS" else "FAILS",
        })
    controls: list[dict[str, Any]] = []
    for control in CONTROLS:
        worst_axis, worst_rate = None, -1.0
        for axis in MEMBERS:
            cell = scored["confusion"][axis].get(control, {"fired": 0, "responses": 0})
            rate = cell["fired"] / cell["responses"] if cell["responses"] else 0.0
            if rate > worst_rate:
                worst_axis, worst_rate = axis, rate
        own = scored["readings"][worst_axis]["own_rate"] if worst_axis else None
        separated = own is not None and worst_rate >= own
        controls.append({
            "family": control,
            "aligned": round(worst_rate, 4),
            "decided_pairs": scored["confusion"][worst_axis].get(
                control, {"responses": 0})["responses"] if worst_axis else 0,
            "p_two_sided": None,
            "attainable_floor": None,
            "k_required": None,
            "worst_axis": worst_axis,
            "rate_on_this_control": round(worst_rate, 4),
            "same_axis_rate_on_its_own_family": own,
            "role": "floor" if control == "placebo_identical" else "void-control",
            "control_verdict": "SEPARATES" if separated else "INDIFFERENT",
            "consequence": (
                ("an axis was named on a pair whose sides are the same string — confabulation at "
                 "or above the rate it is named where it is real"
                 if control == "placebo_identical" else
                 "an axis was named on a formatting-only pair at or above its real rate; that is "
                 "a layout reading and is VOID (§78.1)")
                if separated else "named below its own-family rate, as required"
            ),
        })
    return members, controls


def orientation_symmetry(
    elicited: dict[str, dict[str, list[dict[str, Any]]]], family: str
) -> dict[str, Any]:
    """E6's substitute for the positional precondition, and it is a substitute with a reason.

    E6 asks for no choice, so `positional_bias` has nothing to count and reporting it would be a
    precondition that cannot fail. What *can* go wrong is the same defect in E6's own currency:
    the report channel working in one slot and not the other. So the check is whether the axis
    matcher fires at the same rate with the transformed side shown first and second.
    """
    by_orientation = {0: [0, 0], 1: [0, 0]}
    for rows in elicited.get(family, {}).values():
        for row in rows:
            if row["refused"]:
                continue
            cell = by_orientation[row["orientation"]]
            cell[0] += axis_named(family, row["said"])
            cell[1] += 1
    rates = {
        side: round(cell[0] / cell[1], 4) if cell[1] else None
        for side, cell in by_orientation.items()
    }
    decided = sum(cell[1] for cell in by_orientation.values())
    both = [rate for rate in rates.values() if rate is not None]
    return {
        "precondition": (
            "NO_CHOICE_TO_COUNT" if decided < DECIDED_FLOOR
            else "SYMMETRIC" if len(both) == 2 and abs(both[0] - both[1]) <= 0.2
            else "ASYMMETRIC"
        ),
        "responses": decided,
        "fires_by_orientation": rates,
        "note": "not positional_bias — E6 asks for no choice; see orientation_symmetry",
    }


# --------------------------------------------------------------------------- the report

def control_reading(family: str, signs: dict[str, int]) -> dict[str, Any]:
    """A control's reading. Separation here is a verdict about the protocol, not about the family.

    The two controls fail differently and the wording keeps them apart. `placebo_identical`
    separating means the protocol distinguishes a string from itself; `rewhitespace_sham`
    separating means it is reading layout (§78.1). Both void the protocol, and neither is a
    result about prose.
    """
    reading = family_reading(family, signs)
    separated = reading["verdict"] == "CLEARS"
    reading["role"] = "floor" if family == "placebo_identical" else "void-control"
    reading["control_verdict"] = "SEPARATES" if separated else "INDIFFERENT"
    reading["consequence"] = (
        ("the protocol separates a string from itself; every reading above this is VOID"
         if family == "placebo_identical" else
         "the protocol recovers a formatting-only difference; its readings are a layout "
         "reading and are VOID (§78.1)")
        if separated else "no separation, as required"
    )
    return reading


def positive_control_reading(
    signs: dict[str, int], comparisons: list[Any] | None
) -> dict[str, Any]:
    """`repair_interiority`, read as a preference. Never as a counter alignment (§88).

    Two numbers, because they answer different questions and §85's figure is denominated in the
    second. The pair-level rate with its Clopper-Pearson interval is the one that decides
    "preserved"; the comparison-level win rate is what 0.9509 / 1.0000 / 0.9688 are, and it prints
    beside it so a reader can compare like with like without the entry doing the arithmetic.
    """
    decided_scenes = [scene for scene, sign in signs.items() if sign != 0]
    groups = len(decided_scenes)
    kept = sum(1 for scene in decided_scenes if signs[scene] > 0)
    low, high = clopper_pearson(kept, groups) if groups else (0.0, 1.0)
    win_rate = None
    if comparisons:
        scored = [
            0.5 if c.choice == "neither" else float(c.chose_variant)
            for c in comparisons if not c.refused
        ]
        win_rate = round(statistics.fmean(scored), 4) if scored else None
    return {
        "family": POSITIVE_CONTROL,
        "pairs_preferring_the_repair": kept,
        "decided_pairs": groups,
        "clopper_pearson": [round(low, 4), round(high, 4)],
        "preserved": bool(groups and low > 0.50),
        "comparison_level_win_rate": win_rate,
        "prior_readings": {"haiku_§85": 0.9509, "sonnet_§85.1": 1.0000, "phi4_§87.3": 0.9688},
        "note": (
            "prior readings are cited for what they measured and are not used as a value here "
            "(§79.1); `preserved` is decided only by the interval measured on this run"
        ),
    }


def protocol_verdict(
    families: list[dict[str, Any]], controls: list[dict[str, Any]], positional: dict[str, Any]
) -> dict[str, Any]:
    """The pre-registered decision rule, applied in the order the conditions were declared in."""
    broken = [row["family"] for row in controls if row["control_verdict"] == "SEPARATES"]
    cleared = [row["family"] for row in families if row["verdict"] == "CLEARS"]
    precondition = positional.get("precondition")
    if broken:
        verdict, why = "VOID", f"control separated: {', '.join(broken)}"
    elif precondition == "OUT_OF_BAND":
        verdict, why = "VOID", (
            f"chose-A {positional.get('chose_A_rate')} outside {BIAS_BAND} on "
            f"{positional.get('decided')} decided comparisons"
        )
    elif precondition == "ASYMMETRIC":
        # E6's currency, not E1's: the matcher fires at different rates depending on which slot
        # the transformed side was shown in, so the report channel is position-dependent. Same
        # consequence as a chose-A rate outside the band, reached through the only quantity a
        # protocol that asks for no choice has.
        verdict, why = "VOID", (
            f"the axis matcher fires asymmetrically across orientations "
            f"({positional.get('fires_by_orientation')}); the report channel is reading position"
        )
    elif precondition in ("INSUFFICIENT_DECIDED", "NO_CHOICE_TO_COUNT"):
        verdict, why = "NOT_READABLE", (
            f"{positional.get('decided', positional.get('responses'))} usable comparisons, below "
            f"the {DECIDED_FLOOR} floor (§86.7); a band is not read at this depth"
        )
    elif len(cleared) >= FAMILIES_TO_SURVIVE:
        verdict, why = "SURVIVES", f"cleared {len(cleared)} of {len(families)}: {cleared}"
    else:
        verdict, why = "FAILS", f"cleared {len(cleared)} of {len(families)}, needs "\
                                f"{FAMILIES_TO_SURVIVE}"
    return {"verdict": verdict, "because": why, "families_cleared": cleared}


def assemble(
    name: str, description: str, *, families: dict[str, dict[str, int]],
    positional: dict[str, Any], extra: dict[str, Any] | None = None,
    comparisons_by_family: dict[str, list[Any]] | None = None,
) -> dict[str, Any]:
    """One protocol's whole entry: members, controls, positive control, verdict, both readings."""
    member_rows = [family_reading(name_, families[name_]) for name_ in MEMBERS if name_ in families]
    control_rows = [control_reading(name_, families[name_]) for name_ in CONTROLS
                    if name_ in families]
    positive = (
        positive_control_reading(
            families[POSITIVE_CONTROL],
            (comparisons_by_family or {}).get(POSITIVE_CONTROL),
        ) if POSITIVE_CONTROL in families else None
    )
    verdict = protocol_verdict(member_rows, control_rows, positional)
    return {
        "protocol": name,
        "elicitation": description,
        "positional_precondition": positional,
        "members": member_rows,
        "controls": control_rows,
        "positive_control": positive,
        "verdict": verdict,
        "readings": {
            "as_registered": verdict["verdict"],
            "corrected": verdict["verdict"],
            "note": (
                "as-registered and corrected coincide: no rule in PRE_REGISTRATION was found "
                "unattainable or wrongly specified during this run. Both print anyway (rail 5) "
                "so that a later correction has a slot to appear in rather than replacing a "
                "number that was already published."
            ),
        },
        **(extra or {}),
    }


def seed_cache(target: Path, sources: Sequence[Path]) -> int:
    """Copy prior runs' records into this run's cache so identical requests replay for free.

    Rail 6: one digest-keyed cache per concurrent run, and never re-buy. The records are
    append-only JSONL keyed by request digest, so concatenating is exactly the right operation —
    a record whose digest does not match anything this run asks for is inert, and one that
    matches is a call already paid for. §86.7's shutdown recovered 158 comparisons this way.
    """
    if target.exists():
        return 0
    lines: list[str] = []
    for source in sources:
        if source.is_file():
            lines.extend(source.read_text(encoding="utf-8").splitlines())
    if lines:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


PROTOCOLS: tuple[str, ...] = ("E1", "E2", "E4", "E5", "E6")


def study(args: argparse.Namespace) -> dict[str, Any]:
    """Run the requested protocols and assemble the report. E2 never elicits; it re-reads E1."""
    personas = PANEL[: args.personas]
    families = _fixtures()
    wanted = tuple(args.protocols)
    report: dict[str, Any] = {
        "pre_registration": PRE_REGISTRATION,
        "model": args.model,
        "transport": args.transport,
        "personas": [persona.persona_id for persona in personas],
        "fixtures": {name: len(pairs) for name, pairs in families.items()},
        "protocols": {},
    }
    cache = RESULTS / args.cache
    replayed = seed_cache(cache, [RESULTS / name for name in args.seed_cache])
    if replayed:
        print(f"seeded {cache.name} with {replayed} prior records", file=sys.stderr)

    with Elicitor(
        cache, model=args.model, spot_model=None, spot_fraction=0.0, effort=None,
        transport=args.transport, pair_question="preference", dry_run=args.dry_run,
        max_workers=args.workers,
    ) as elicitor:
        pairwise: dict[str, dict[str, list[Any]]] | None = None
        if "E1" in wanted or "E2" in wanted:
            pairwise = run_pairwise(elicitor, families, personas)
            flat = {f: [c for cs in by.values() for c in cs] for f, by in pairwise.items()}
            every = [c for cs in flat.values() for c in cs]
            if "E1" in wanted:
                signs, detail = score_choices(pairwise, tie_policy="half_win")
                report["protocols"]["E1"] = assemble(
                    "E1", "pairwise forced choice, ties scored as half a win — the incumbent",
                    families=signs, positional=bias_reading(every, has_slot=True),
                    extra={"tie_accounting": detail}, comparisons_by_family=flat,
                )
            if "E2" in wanted:
                signs, detail = score_choices(pairwise, tie_policy="drop")
                report["protocols"]["E2"] = assemble(
                    "E2", "the same records, ties dropped and read as calibrated indifference "
                          "(B3) — a re-read of E1 and not a second purchase",
                    families=signs, positional=bias_reading(every, has_slot=True),
                    extra={"tie_accounting": detail, "elicitation_shared_with": "E1"},
                    comparisons_by_family=flat,
                )
        if "E4" in wanted:
            elicited = run_scalar(elicitor, families, personas)
            signs, detail = score_scalar(elicited)
            report["protocols"]["E4"] = assemble(
                "E4", f"single-text scalar rating 0-{E4_SCALE}, each side alone, paired "
                      "difference — no pair in the prompt at all",
                families=signs, positional=bias_reading([], has_slot=False),
                extra={"scalar_accounting": detail},
            )
        if "E5" in wanted:
            elicited = run_two_stage(elicitor, families, personas)
            every = [c for by in elicited.values() for cs in by.values() for c in cs]
            flat = {f: [c for cs in by.values() for c in cs] for f, by in elicited.items()}
            signs, detail = score_choices(elicited, tie_policy="half_win")
            report["protocols"]["E5"] = assemble(
                "E5", "describe each passage in turn, then the identical E1 choice",
                families=signs, positional=bias_reading(every, has_slot=True),
                extra={"tie_accounting": detail}, comparisons_by_family=flat,
            )
        if "E6" in wanted:
            elicited = run_verbalize(elicitor, families, personas)
            matcher = score_verbalize(elicited)
            members, controls = verbalize_rows(elicited, matcher)
            symmetry = {name: orientation_symmetry(elicited, name) for name in MEMBERS}
            worst = max(
                symmetry.values(),
                key=lambda row: {"ASYMMETRIC": 2, "NO_CHOICE_TO_COUNT": 1, "SYMMETRIC": 0}[
                    row["precondition"]],
            )
            report["protocols"]["E6"] = {
                "protocol": "E6",
                "elicitation": ("name the single most salient difference; scored by a matcher "
                                "frozen before the run, against a null measured in the same run"),
                "positional_precondition": worst,
                "members": members,
                "controls": controls,
                "positive_control": None,
                "verdict": protocol_verdict(members, controls, worst),
                "matcher": matcher,
                "orientation_symmetry": symmetry,
                "statistic": (
                    "one-sided Fisher exact, not the two-sided sign test the other protocols "
                    "use. Only firing is evidence here, so the direction is not arbitrary and "
                    "the null is the matcher's own unprompted rate rather than 1/2"
                ),
                "readings": {
                    "as_registered": "the Fisher test, as declared in PRE_REGISTRATION.e6_null",
                    "corrected": (
                        "unchanged. The sign-test scoring that the other five protocols share was "
                        "written for E6 as well and removed before any response existed: it "
                        "rewards consistent silence exactly as much as consistent naming, so a "
                        "matcher that never fires reads k=G and prints CLEARS. Recorded because a "
                        "later reader will otherwise wonder why E6 alone is scored differently."
                    ),
                },
            }
        report["spend"] = elicitor.spend()
        report["calls"] = {
            "api": elicitor.api_calls,
            "replayed": elicitor.replayed,
            # Not cached, so a resume re-issues exactly these. Reported beside the verdict rather
            # than folded into the refusals: a call that obtained no answer is not a model
            # declining to answer, and §87.3 is the entry that had to make that distinction after
            # the fact. A non-zero count means the verdict describes the cells that answered.
            "transport_failures": elicitor.transport_failures,
        }

    survivors = [name for name, entry in report["protocols"].items()
                 if entry["verdict"]["verdict"] == "SURVIVES"]
    report["verdict"] = {
        "survivors": survivors,
        "reading": (
            f"{len(survivors)} of {len(report['protocols'])} protocols carried a difference B6 "
            "certifies is present, on at least two families, with both controls indifferent."
            if survivors else
            "No protocol carried the difference. The composite instrument (§3 of the directive) "
            "is the correct architecture by measurement rather than by adoption, and verdict-tier "
            "climbing ends with a citation instead of a budget."
        ),
        "licenses": (
            "Nothing. B6's counter is a discrimination oracle, not a taste; §82 governs verbatim "
            "and PREFERENCE remains a human's blinded choice. A surviving protocol is a candidate "
            "for JudgeBench A2's verdict layer and nothing more."
        ),
    }
    return report


def selftest() -> int:
    """The arithmetic, checked before it is pointed at anything expensive."""
    failures: list[str] = []

    def check(claim: str, ok: bool) -> None:
        if not ok:
            failures.append(claim)

    check("a perfect family hits exactly 2/2**G", exact_two_sided(8, 8) == 2 / 256)
    check("the floor is unattainable below G=6", required_k(5) is None)
    check("G=6 needs all six", required_k(6) == 6)
    for groups, needed in ((10, 9), (9, 8), (7, 7)):
        check(f"G={groups} needs k={needed}", required_k(groups) == needed)
    check("the statistic is symmetric", exact_two_sided(2, 10) == exact_two_sided(8, 10))
    check("an even split is p=1", exact_two_sided(5, 10) == 1.0)
    check("a tie leaves the denominator", sign_of(0.5) == 0 and sign_of(None) == 0)
    check("above indifference is +1", sign_of(0.75) == 1 and sign_of(0.25) == -1)
    # Checked against `scipy.stats.fisher_exact(..., alternative="greater")` under the MirrorBench
    # interpreter, which is the one that has scipy; the values are pinned rather than bounded so a
    # rewrite of the hypergeometric sum cannot drift. An earlier draft asserted 1.0 for equal
    # rates, which is wrong — the one-sided p at the mean of a discrete distribution is 0.67, not
    # 1.0 — and the selftest caught it before any response existed to score.
    for table, expected in (
        ((5, 5, 5, 5), 0.6718591007),        # identical rates: not significant, and not 1.0
        ((10, 0, 0, 10), 0.0000054125),      # a clean split
        ((8, 2, 3, 17), 0.0009742382),
        ((0, 10, 10, 0), 1.0),               # backwards: the one-sided test must not reward it
    ):
        check(f"fisher {table} = {expected}", abs(fisher_exact_greater(*table) - expected) < 1e-9)
    check("stat matcher fires on numbers",
          axis_named("stat_flatten", "B has no numbers in the status block"))
    check("stat matcher is quiet on prose about voice",
          not axis_named("stat_flatten", "one narrator sounds warmer than the other"))
    check("interiority matcher fires",
          axis_named("interiority_strip_matched", "A gives us his thoughts; B does not"))
    check("em-dash matcher fires", axis_named("repair_emdash", "A uses em dashes where B uses "
                                              "full stops"))
    check("E5 stage 2 is E1's question verbatim", E5_STAGE2.startswith("Two passages. Which one"))
    for name in MEMBERS:
        check(f"{name} has a frozen matcher", name in AXIS_MATCHERS)
        check(f"{name} is decidable enough to test",
              len(decidable(name)) >= PRE_REGISTRATION["minimum_groups"])
    for message in failures:
        print(f"  FAIL {message}", file=sys.stderr)
    print(f"selftest: {'PASS' if not failures else str(len(failures)) + ' FAILURES'}",
          file=sys.stderr)
    return 1 if failures else 0


def _cell(value: object, width: int = 9) -> str:
    """One table cell. An em dash where a statistic does not apply, never a fabricated zero."""
    if value is None:
        return f"{'--':>{width}s}"
    return f"{value:>{width}.5f}" if isinstance(value, float) else f"{value!s:>{width}s}"


def render(report: dict[str, Any]) -> None:
    """The table the ledger entry is written from."""
    print(f"\nmodel {report['model']} via {report['transport']}, personas "
          f"{report['personas']}")
    for name, entry in report["protocols"].items():
        verdict = entry["verdict"]
        print(f"\n{name}  {entry['elicitation']}")
        print(f"  precondition {entry['positional_precondition']['precondition']}"
              f"  ->  {verdict['verdict']}: {verdict['because']}")
        print(f"  {'family':28s} {'k/G':>9s} {'p':>9s} {'floor':>9s} {'need':>5s}  verdict")
        for row in entry["members"] + entry["controls"]:
            # E6's rows carry a rate and a Fisher p where the rest carry a count and an exact
            # binomial p, and its controls carry neither a floor nor a required k. Formatted
            # defensively rather than in two loops: a protocol scored on a different statistic
            # still belongs in the table the ledger entry is written from.
            counted = (f"{row['aligned']:>4d}/{row['decided_pairs']:<4d}"
                       if isinstance(row["aligned"], int) else f"{row['aligned']:>9.4f}")
            print(f"  {row['family']:28s} {counted} {_cell(row['p_two_sided'])} "
                  f"{_cell(row['attainable_floor'])} {_cell(row['k_required'], 5)}  "
                  f"{row.get('control_verdict', row.get('verdict'))}")
        positive = entry.get("positive_control")
        if positive:
            print(f"  {positive['family']:28s} {positive['pairs_preferring_the_repair']:>3d}/"
                  f"{positive['decided_pairs']:<3d} CI {positive['clopper_pearson']} "
                  f"preserved={positive['preserved']} win={positive['comparison_level_win_rate']}")
    spend = report.get("spend", {})
    print(f"\ncalls {report.get('calls')}  equivalent ${spend.get('equivalent_usd')}")
    print(f"verdict: {report['verdict']['reading']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocols", nargs="+", default=list(PROTOCOLS), choices=PROTOCOLS)
    parser.add_argument("--model", default="claude-haiku-4-5")
    parser.add_argument("--transport", default="cli", choices=("cli", "ollama", "sdk"))
    parser.add_argument("--personas", type=int, default=2)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--cache", default="elicitation-study-raw.jsonl")
    parser.add_argument("--seed-cache", nargs="*", default=[],
                        help="prior raw JSONL files whose matching requests replay for free")
    parser.add_argument("--out", default="elicitation-study.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--yes", action="store_true", help="required for a run that spends")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if selftest():
        print("refusing to run: the arithmetic selftest failed", file=sys.stderr)
        return 1
    if not args.dry_run and not args.yes:
        print("this run spends; pass --yes", file=sys.stderr)
        return 2

    started = time.time()
    report = study(args)
    report["seconds"] = round(time.time() - started, 1)
    out = RESULTS / args.out
    out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    render(report)
    print(f"\nwrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
