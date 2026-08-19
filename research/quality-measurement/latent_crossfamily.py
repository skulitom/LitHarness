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
        "Deliberately a screen. At the default 32 comparisons the standard error on a bias "
        "estimate is about 0.088, which separates a 0.80-biased judge from an unbiased one at "
        "roughly 3.4 standard errors and does NOT resolve a candidate sitting near the band edge. "
        "A candidate that lands inside the band here is a candidate worth funding a real arm on, "
        "never a candidate that has passed."
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
    if not every or refused == len(every):
        status = "NOT_SCREENABLE"
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
        "win_rate": (
            round(statistics.fmean(rates), 4) if status == "ELIGIBLE" and rates
            else "WITHHELD — see PRE_REGISTRATION.withholding_rule"
        ),
    }
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
    parser.add_argument("--personas", type=int, default=2,
                        help="personas seated; 2 x 8 scenes x 2 orientations = 32 comparisons")
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
