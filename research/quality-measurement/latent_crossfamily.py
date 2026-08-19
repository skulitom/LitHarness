"""Which non-Anthropic judges are even eligible to answer Track S's question?

Track S asks whether panel preference tracks generator-judge **family match** — machine taste for
the model's own register. Answering it needs a cross-family judge, and the directive reserves the
*choice* of one to the operator: cost, terms and protocol fidelity are a policy call. This module
does not make that call and does not read a preference. It measures the one thing that decides
**eligibility**, on our own pairs, for free.

**Why a screen exists at all, rather than an inherited figure.** §79.1's closing rule is that
positional bias is a property of the pair as much as of the panel, so *"any future use of this
instrument on this kind of material has to measure bias on its own pairs; inheriting a figure from
a different experiment remains unsupported."* RUNBOOK records `gemma3:4b` failing the precondition
at chose-A 0.802/0.810 — but that was §70's material, ~1,000-word passages of `toll.db` against
their own ablations, not §85's certified repair pairs. Citing it to rule the track out would be
exactly the inheritance §79.1 forbids, and stage-0 §87.1 did cite it that way. This module is the
correction.

**What it produces and what it refuses to produce.** One number per candidate: the rate at which
it picks the first slot, over both orientations of the same pairs. That is a precondition, not a
verdict. Win rates are computed and **withheld from the report** unless the bias precondition
passes, because a preference read off a positionally-biased judge is what §83, §85 and §79.1 each
had to void — and because reading one here would pre-empt the operator's reserved choice by
turning a screen into a result.

**The candidate set is whatever is already on this machine.** No download, no API key, no quota:
`ollama list`. That is also the honest scope — a screen over four local models says nothing about
the frontier non-Anthropic judges the operator might prefer, and the report says so.

Local inference only. The GPU governor from `cdg_battery` applies through `Elicitor`'s own
`rest_ratio`, and a 20B model on ~2,000-token prompts is minutes per handful of comparisons, so
this is scoped as a screen rather than an arm.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from elicit import Elicitor, positional_bias  # noqa: E402
from latent_fixtures import build_families, drop_degenerate  # noqa: E402
from personas import PANEL  # noqa: E402

RESULTS = HERE / "results"

#: The pre-registered band, taken verbatim from §78.2 and used unchanged by §83, §85 and §79.1.
#: A candidate outside it cannot be read for preference on this material by anyone.
BIAS_BAND = (0.40, 0.60)

#: The fixture the screen runs on: §85's interiority repair pairs, which are the exact pairs
#: Track S would put to a cross-family judge. Screening on a *different* fixture would reproduce
#: the inheritance problem this module exists to fix.
SCREEN_FAMILY = "repair_interiority"

#: §86.7's floor: a rate is not read as a band below this many **decided** comparisons.
#:
#: **§87.3 is why this is a constant rather than a caveat.** That screen disqualified `gemma3:4b`
#: on a chose-A rate of 1.000 — perfectly positional — and the honest sentence had to be written
#: in prose beside it: the rate rested on **eleven** decisions, because the model answered
#: `neither` to the other twenty-one. The disqualification was right and the number was thin, and
#: nothing in the code said so. A judge that mostly abstains and is perfectly positional on the
#: few it decides is a different object from one that answers every comparison from the first
#: slot, and a screen that returns the same status for both is not measuring eligibility.
#:
#: So `INSUFFICIENT_DECIDED` is its own state, on the same principle as `NOT_SCREENABLE`: a
#: candidate that did not decide enough to be read is neither eligible nor disqualified, and
#: reporting it as either would put a number where there is not one.
DECIDED_FLOOR = 30

#: **A correction to the floor above, made the day the floor was written, because seating four
#: personas turned out not to buy four times the evidence.**
#:
#: `DECIDED_FLOOR` counts *comparisons*. Stage-0 §89 screened `qwen3:14b` at 4 personas x 8 scenes
#: x 2 orientations and got 64 decided comparisons — and **one distinct answer vector across all
#: four personas**, byte-identical. The model ignores the persona system prompt, so the panel is
#: one judge replicated four times and the 64 comparisons are 16 independent decisions. A rate
#: computed over them has the precision of 16, not of 64.
#:
#: That is §87.3's lesson in a second costume. There the inflated number came from abstention —
#: 1.000 resting on eleven decisions — and here it comes from replication, which is harder to see
#: because nothing is missing from the table. So the independent unit is the **(pair, orientation)
#: cell**, personas are replicates on it, and both readings print: the as-registered count and the
#: independent-cell count, with the status each implies.
#:
#: The consequence is worth stating plainly rather than repairing: on an 8-pair fixture there are
#: 16 cells, so **a judge that ignores personas cannot reach a 30-decision floor on this material
#: at all**, however many personas are seated. That is the fourth bar in this project's history
#: whose own design could not reach it (§81, §85, §87, this), and it is recorded rather than
#: lowered.
INDEPENDENT_UNIT = "(pair, orientation) cell; personas are replicates when they answer alike"


def _persona_degeneracy(comparisons: list[Any]) -> dict[str, Any]:
    """Do the seated personas answer differently, or is this one judge wearing four hats?"""
    by_persona: dict[str, dict[tuple[str, int], str | None]] = {}
    for row in comparisons:
        by_persona.setdefault(row.persona_id, {})[(row.pair_id, row.orientation)] = row.choice
    cells = sorted({cell for mine in by_persona.values() for cell in mine})
    vectors = {
        persona: tuple(mine.get(cell) for cell in cells) for persona, mine in by_persona.items()
    }
    distinct = len(set(vectors.values()))
    decided_cells = sum(
        1 for cell in cells
        if any(vectors[p][i] in ("A", "B") for i, c in enumerate(cells) if c == cell
               for p in vectors)
    )
    return {
        "personas_seated": len(vectors),
        "distinct_answer_vectors": distinct,
        "degenerate": distinct < len(vectors),
        "independent_cells": len(cells),
        "decided_cells": decided_cells,
        "unit": INDEPENDENT_UNIT,
        "per_persona_chose_A": {
            persona: round(
                sum(1 for v in vec if v == "A") / max(sum(1 for v in vec if v in ("A", "B")), 1), 4
            )
            for persona, vec in sorted(vectors.items())
        },
    }


PRE_REGISTRATION: dict[str, Any] = {
    "written": "2026-08-19, before the first local elicitation",
    "measures": "positional bias only — the eligibility precondition, not a preference.",
    "band": list(BIAS_BAND),
    "withholding_rule": (
        "Win rates are computed and NOT reported for any candidate whose bias falls outside the "
        "band. A preference read off a positionally-biased judge is what §83, §85's em-dash arm "
        "and §79.1 each had to void, and printing one here would also pre-empt the operator's "
        "reserved choice of cross-family judge."
    ),
    "power": (
        "Deliberately a screen. At the default 64 comparisons the standard error on a bias "
        "estimate is about 0.063, which separates a 0.80-biased judge from an unbiased one at "
        "roughly 4.8 standard errors and still does NOT resolve a candidate sitting near the band "
        "edge — 0.40 and 0.50 are 1.6 standard errors apart. A candidate that lands inside the "
        "band here is a candidate worth funding a real arm on, never a candidate that has passed. "
        "(The figure was 0.088 at the 32 comparisons this screen defaulted to for §87.3; the "
        "default moved with `decided_floor` and this sentence moved with it.)"
    ),
    "decided_floor": (
        "A chose-A rate is read as a band only on at least 30 decided comparisons (§86.7). Below "
        "that the candidate is INSUFFICIENT_DECIDED, which is neither eligible nor disqualified: "
        "§87.3 disqualified `gemma3:4b` on a rate resting on eleven decisions and had to say so "
        "in prose, and a state the code cannot express is a state the next run will get wrong. "
        "The screen is therefore seated at four personas — 4 x 8 scenes x 2 orientations = 64 "
        "comparisons — so a candidate abstaining on half of them still clears the floor. §87.3's "
        "figures were taken at two personas on the same material and are cited as prior context, "
        "never used as a value here (§79.1)."
    ),
    "reserved": (
        "Which cross-family judge is acceptable — cost, terms, protocol fidelity — is the "
        "operator's call (directive §6). This module narrows the field to the eligible; it does "
        "not choose from it."
    ),
}

#: Candidates the operator has ruled out on **acceptability**, which is the reserved half of the
#: question and not something a screen can decide. Recorded here so a later reader sees why an
#: eligible model is not being funded, and so the exclusion is not silently re-litigated.
#:
#: Operator, 2026-08-19: *"let's ignore gpt oss it's too old anyway, like phi4"*. Both predate the
#: current generation by a wide margin — `phi4` is a 2024-era 14B and `gpt-oss:20b` additionally
#: fails to load on this machine. Their numbers stay in the report because a measurement taken
#: under a passing precondition is still a measurement; their status as *candidates* is closed.
OPERATOR_EXCLUDED: dict[str, str] = {
    "gpt-oss:20b": "operator: too old; also NOT_SCREENABLE on this machine (weights fail to load)",
    "phi4:latest": "operator: too old to serve as Track S's cross-family judge",
}


def screen(model: str, args: argparse.Namespace) -> dict[str, Any]:
    """One candidate, one fixture, both orientations. Bias out; preference withheld."""
    families = build_families()
    pairs, _ = drop_degenerate(SCREEN_FAMILY, families[SCREEN_FAMILY])
    pairs = pairs[: args.scenes]
    personas = PANEL[: args.personas]

    every: list[Any] = []
    rates: list[float] = []
    cache = RESULTS / f"crossfamily-{model.replace(':', '-').replace('/', '-')}-raw.jsonl"
    with Elicitor(
        cache, model=model, spot_model=None, spot_fraction=0.0, effort=None,
        transport="ollama", pair_question="preference", dry_run=args.dry_run,
        rest_ratio=args.rest_ratio,
    ) as elicitor:
        for pair in pairs:
            # The negative side is the original and the positive the repair, matching how §85
            # posed it, so a future arm compares like with like rather than re-deriving a sign.
            comparisons = elicitor.compare_pair(
                f"{pair.scene}|{SCREEN_FAMILY}", pair.negative, pair.positive,
                n=1, personas=personas,
            )
            every.extend(comparisons)
            scored = [
                0.5 if c.choice == "neither" else float(c.chose_variant)
                for c in comparisons if not c.refused
            ]
            if scored:
                rates.append(statistics.fmean(scored))
            print(f"  {model} {pair.scene}: {len(every)} comparisons", file=sys.stderr, flush=True)

    bias = positional_bias(every)
    # `chose_A_rate`, and it is NaN when nothing was decided. Both cases must fail the band
    # rather than pass it: the first draft read a key that does not exist, got None, and reported
    # every candidate ineligible — a screen that cannot pass is as useless as one that cannot fail.
    value = bias.get("chose_A_rate")
    numeric = isinstance(value, float) and value == value  # NaN is the only float unequal to itself
    in_band = numeric and BIAS_BAND[0] <= float(value) <= BIAS_BAND[1]
    refused = sum(1 for c in every if c.refused)

    # **Three outcomes, not two.** `gpt-oss:20b` returned 32 of 32 transport errors on this
    # machine — the weights fail to load ("tensor size overflow"), so no judgment was ever
    # obtained. Folding that into "ineligible" would report a model as having answered a slot
    # when it never answered at all, and would let a broken install masquerade as evidence about
    # judges. NOT_SCREENABLE is its own state and it is a fact about this machine, not the model.
    decided = int(bias.get("decided", 0) or 0)
    degeneracy = _persona_degeneracy([c for c in every if not c.refused])
    # The corrected count, and it is unconditional rather than conditional on degeneracy.
    #
    # The first draft used cells only when the personas answered alike, which is the wrong rule
    # for a reason `elicitation_study.PRE_REGISTRATION` states about itself the same morning:
    # *personas and orientations within a pair are repeated measures on the same scene, not
    # independent draws, and pooling them would inflate every p-value by the replication factor.*
    # Orientation is part of the stimulus here — it is the thing bias is *about* — so the unit is
    # the (pair, orientation) cell and personas are replicates on it whether or not they happen to
    # agree. Four personas that differ are still four correlated readings of sixteen cells.
    #
    # Applying it only to degenerate panels would have been a rule chosen after seeing which
    # candidate it rescued, which is what §81 refused to do.
    effective = degeneracy["decided_cells"]
    if not every or refused == len(every):
        status = "NOT_SCREENABLE"
    elif effective < DECIDED_FLOOR:
        # Four outcomes now, and this is the one §87.3 had to write in prose. A candidate that
        # abstained its way below the floor has not been shown eligible *or* biased: the band is
        # simply not readable at that depth, and forcing it into either verdict would report a
        # measurement nobody took.
        status = "INSUFFICIENT_DECIDED"
    elif in_band:
        status = "ELIGIBLE"
    else:
        status = "INELIGIBLE_ON_BIAS"

    row: dict[str, Any] = {
        "model": model,
        "comparisons": len(every),
        "refused": refused,
        "status": status,
        "positional_bias": bias,
        "in_band": in_band,
        "eligible": status == "ELIGIBLE",
        "decided": decided,
        "decided_floor": DECIDED_FLOOR,
        "persona_degeneracy": degeneracy,
        "effective_decisions": effective,
        "readings": {
            "as_registered": (
                "ELIGIBLE" if in_band and decided >= DECIDED_FLOOR
                else "INSUFFICIENT_DECIDED" if decided < DECIDED_FLOOR else "INELIGIBLE_ON_BIAS"
            ),
            "corrected": status,
            "note": (
                "as-registered counts comparisons; corrected counts independent cells, because "
                "personas that answer alike are replicates. Both print (rail 5) and nothing "
                "retro-passes."
            ),
        },
        # **The code gate was stricter than the declared rule, and the declared rule governs.**
        # `PRE_REGISTRATION["withholding_rule"]` withholds a win rate *"for any candidate whose
        # bias falls outside the band"*, and the reason it gives is that a preference read off a
        # positionally-biased judge is what §83, §85 and §79.1 each had to void. The first draft
        # gated on `status == "ELIGIBLE"` instead, which also withholds from a candidate that
        # cleared the band and merely lacks depth — a different failure with a different remedy.
        #
        # Aligning the code to the pre-registration rather than the pre-registration to the code:
        # a candidate inside the band gets its number printed with the precision that produced it
        # attached, which is what §87.3 did with `phi4`'s 0.9688 ("heavily qualified — 32
        # comparisons, two personas, a model the operator has closed"). Suppressing a figure that
        # was legitimately obtained under the declared condition would be moving a rule after
        # seeing what it hid.
        "win_rate": (
            round(statistics.fmean(rates), 4) if in_band and rates
            else "WITHHELD — bias outside the band; see PRE_REGISTRATION.withholding_rule"
        ),
        "win_rate_precision": (
            f"read on {degeneracy['decided_cells']} independent cells, not "
            f"{decided} comparisons; the standard error on a rate here is about "
            f"{(0.25 / max(degeneracy['decided_cells'], 1)) ** 0.5:.3f}"
        ),
    }
    if status == "INSUFFICIENT_DECIDED":
        row["insufficient_because"] = (
            f"{effective} independent decisions, below the {DECIDED_FLOOR} floor. "
            + (f"{decided} of {len(every)} comparisons were decided, but the "
               f"{degeneracy['personas_seated']} seated personas produced "
               f"{degeneracy['distinct_answer_vectors']} distinct answer "
               f"vector(s) — the panel is one judge replicated, so the evidence is "
               f"{degeneracy['decided_cells']} cells and not {decided} comparisons."
               if degeneracy["degenerate"] else
               f"the candidate answered `neither` to {len(every) - decided - refused} and refused "
               f"{refused}.")
            + " Neither eligible nor disqualified — the band is not readable here."
        )
    if status == "NOT_SCREENABLE":
        # `Comparison` carries no stop reason — that lives in the cache record beside it, which is
        # where a reader has to look anyway to tell a refusal from a transport failure.
        row["not_screenable_because"] = f"every comparison refused; see {cache.name}"
        row["cache"] = cache.name
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--models", nargs="+", default=["gpt-oss:20b"],
                        help="ollama tags already pulled on this machine")
    parser.add_argument("--scenes", type=int, default=8)
    parser.add_argument("--personas", type=int, default=4,
                        help="personas seated; 4 x 8 scenes x 2 orientations = 64 comparisons, "
                             "which keeps a half-abstaining candidate above the 30-decided floor")
    parser.add_argument("--rest-ratio", type=float, default=1.0,
                        help="this box thermal-shuts-down under sustained local inference")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out", default=str(RESULTS / "latent-crossfamily-screen.json"))
    args = parser.parse_args(argv)

    report: dict[str, Any] = {
        "pre_registration": PRE_REGISTRATION,
        "family": SCREEN_FAMILY,
        "candidates": [screen(model, args) for model in args.models],
    }
    def named(status: str) -> list[str]:
        return [row["model"] for row in report["candidates"] if row["status"] == status]

    for row in report["candidates"]:
        if row["model"] in OPERATOR_EXCLUDED:
            row["operator_excluded"] = OPERATOR_EXCLUDED[row["model"]]

    # Eligibility is what a screen decides; acceptability is not. A model the operator has closed
    # cannot carry the track however clean its bias, so it is removed from the fundable set here
    # rather than argued with.
    eligible = [m for m in named("ELIGIBLE") if m not in OPERATOR_EXCLUDED]
    biased = named("INELIGIBLE_ON_BIAS")
    broken = named("NOT_SCREENABLE")
    report["operator_excluded"] = OPERATOR_EXCLUDED
    tail = (
        (f" Answered a slot rather than a text: {', '.join(biased)}." if biased else "")
        + (f" Could not be elicited from on this machine at all: {', '.join(broken)}." if broken
           else "")
    )
    report["reading"] = (
        (f"ELIGIBLE (bias in band, preference still unread): {', '.join(eligible)}. Track S may be "
         "funded on one of these at the operator's choice." if eligible else
         "NO LOCAL CANDIDATE IS ELIGIBLE, so the directive's kill condition is DISCHARGED BY "
         "MEASUREMENT rather than asserted: Track S waits on a judge the operator selects, and no "
         "degraded protocol is substituted to force a number.") + tail
    )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report["candidates"], indent=2, sort_keys=True))
    print("\nREADING:", report["reading"])
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
