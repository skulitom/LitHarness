"""B6, admitted: the counter-decidable / panel-undecided benchmark.

§87 proposed a fixture family and refused to admit it — *"It is proposed and not admitted. Only
the operator moves what panel v2 is selected on"* (§84). The operator admitted it on 2026-08-19.
This module is that admission, written as an artifact for the same reason `propose_b6` was: so
that using B6 is a decision somebody made and can be checked against, rather than a membership
re-derived from a results file every time something wants it.

**What B6 is.** Three fixture families where a counter named in advance orders every decidable
pair and the panel did not decide them. It is a benchmark for *instruments*, and the thing it
measures is whether an instrument's channel carries a difference that is provably present in the
material. The counter is the ground truth for **a difference existing on a named axis** — nothing
more. It is not a quality label, it is not a reader, and no ranking on it moves a licence: §82
governs verbatim and classes preference as a human's blinded choice.

**What admission changes and what it does not.** It changes which fixtures an experiment may
select an instrument on. It does not change §84's freeze rule, it does not upgrade BEHAVIOUR-class
evidence, and it does not make the counter a judge. `propose_b6` derived the membership from
§87's run; :func:`verify_against_proposal` checks that what is admitted here is still what was
proposed there, so the two cannot drift apart silently.

Local, deterministic, no quota, no GPU. Runs under `uv run python`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from latent_fixtures import (  # noqa: E402
    Pair,
    build_families,
    drop_degenerate,
    p0_features,
)
from latent_probe import A_PRIORI_COUNTER, PANEL_VERDICTS  # noqa: E402

RESULTS = HERE / "results"

#: The proposal this admits, and where it came from. `b6_proposal` is emitted by
#: `latent_probe.propose_b6` into the probe's results file; §87 records the run that produced it.
PROPOSAL_ARTIFACT = RESULTS / "latent-taste-probe.json"
PROPOSAL_KEY = "b6_proposal"

#: The operator's decision, quoted rather than paraphrased. §84 reserves this act, so the record
#: of it is the licence to use these fixtures at all, and a paraphrase would put the agent's
#: wording where the operator's belongs.
ADMISSION: dict[str, Any] = {
    "decided": "2026-08-19",
    "by": "operator",
    "decision": "ADMIT",
    "quote": (
        "B6: ADMIT. All three members, a priori counters as proposed in "
        "results/latent-taste-probe.json. Record the admission as its own ledger entry before "
        "any E-track arm uses them."
    ),
    "proposed_in": "§87 (stage-0), artifact emitted by latent_probe.propose_b6",
    "recorded_in": "§88 (stage-0)",
    "reserved_by": "§84 — only the operator moves what panel v2 is selected on",
}

#: The admitted membership: family -> the counter named before any result was read. Restated here
#: rather than imported wholesale from :data:`A_PRIORI_COUNTER`, because that mapping also carries
#: families B6 rejected (`repair_interiority`, `filler_inject`) and an admission that said "every
#: family with a counter" would admit two the operator did not admit.
MEMBERS: dict[str, str] = {
    "stat_flatten": "system_digit_count",
    "interiority_strip_matched": "interior_per_1k",
    "repair_emdash": "em_per_1k",
}

#: Mandatory controls for anything measured on B6, and they are not symmetric.
#:
#: `placebo_identical` is the floor: both sides are the same string, so an instrument that
#: separates it is separating nothing and every number above it is void (§85's floor, §87's
#: `k=0` on all four channels).
#:
#: `rewhitespace_sham` is the **void** control rather than a floor, and the difference is the
#: entry §87 had to write against itself. It differs only in formatting; §78.1 measured why it
#: cannot be a floor and §81 said so in terms. An instrument that "recovers" discrimination here
#: is reading layout, and that reading is VOID — not weakened, not caveated.
CONTROLS: tuple[str, ...] = ("placebo_identical", "rewhitespace_sham")

#: The positive control. Not a B6 member — B6 requires the panel to have *failed*, and the panel
#: decides this family — so it rides along as the thing every instrument should keep: 0.9509 at
#: Haiku (§85), 1.0000 at Sonnet (§85.1), 0.9688 at `phi4` (§87.3), three judge families.
#:
#: **It is scored as a preference and never as a counter alignment, and the reason is measured
#: rather than stylistic.** See :func:`counter_deltas`: `interior_per_1k` moves the *wrong way*
#: on `gen:scene-5`, because the repair adds interiority and adds words with it (+11.8% by §87.1)
#: and a per-1k density can fall while the absolute count rises. So the counter reads 7 of 8 on
#: a family three judges read at 0.95-1.00, and scoring the positive control against its counter
#: would import a length confound into the one arm that exists to be clean.
POSITIVE_CONTROL = "repair_interiority"

#: The scene `repair_emdash` cannot score, listed as an id rather than counted as a miss.
#: `gen:scene-7`'s original had no prose em dashes to remove, so both sides read 0.0 and the pair
#: is unscoreable rather than failed — §87's rule, kept because an instrument that is asked to
#: order a tie and does not is not wrong.
STRUCTURAL_TIES: dict[str, tuple[str, ...]] = {"repair_emdash": ("gen:scene-7",)}


def admitted_families() -> dict[str, list[Pair]]:
    """The three admitted members, degenerate pairs already dropped."""
    families = build_families()
    return {name: drop_degenerate(name, families[name])[0] for name in MEMBERS}


def control_families() -> dict[str, list[Pair]]:
    """The two mandatory controls plus the positive control, degenerates dropped.

    `placebo_identical` keeps its byte-identical pairs: there the identity *is* the fixture, and
    `drop_degenerate` exempts it by name for that reason.
    """
    families = build_families()
    names = (*CONTROLS, POSITIVE_CONTROL)
    return {name: drop_degenerate(name, families[name])[0] for name in names}


def counter_deltas(family: str) -> list[dict[str, Any]]:
    """Per-pair movement of one family's a-priori counter, negative side to positive side.

    `sign` is `+1`, `-1`, or `0`; a `0` is a pair the counter cannot decide and it is excluded
    from every count downstream rather than scored as a failure.
    """
    counter = A_PRIORI_COUNTER.get(family)
    if counter is None:
        raise KeyError(f"{family} has no a-priori counter")
    rows = []
    for pair in admitted_families().get(family) or control_families()[family]:
        after = p0_features(pair.positive, steelman=True)[counter]
        before = p0_features(pair.negative, steelman=True)[counter]
        delta = after - before
        rows.append({
            "scene": pair.scene,
            "counter": counter,
            "negative": round(before, 4),
            "positive": round(after, 4),
            "delta": round(delta, 4),
            "sign": 0 if delta == 0 else (1 if delta > 0 else -1),
        })
    return rows


def decidable(family: str) -> list[str]:
    """Scenes whose counter delta is non-zero, in fixture order. The denominator for every test."""
    return [row["scene"] for row in counter_deltas(family) if row["sign"] != 0]


def verify_against_proposal() -> dict[str, Any]:
    """Is what is admitted still what was proposed? Membership, counters, and decidable counts.

    An admission that drifts from its proposal is an admission of something the operator did not
    read. This is the check that makes :data:`ADMISSION` a decision about a specific artifact
    rather than about a name.
    """
    if not PROPOSAL_ARTIFACT.is_file():
        return {"status": "ARTIFACT_ABSENT", "artifact": str(PROPOSAL_ARTIFACT),
                "note": "run latent_probe.py --score to regenerate it; nothing is verified"}
    proposal = json.loads(PROPOSAL_ARTIFACT.read_text(encoding="utf-8"))[PROPOSAL_KEY]
    proposed = {row["family"]: row for row in proposal["members"]}
    problems: list[str] = []
    if set(proposed) != set(MEMBERS):
        problems.append(f"membership differs: proposed {sorted(proposed)}, admitted "
                        f"{sorted(MEMBERS)}")
    for family, counter in MEMBERS.items():
        row = proposed.get(family)
        if row is None:
            continue
        if row["a_priori_counter"] != counter:
            problems.append(f"{family}: proposed counter {row['a_priori_counter']!r}, admitted "
                            f"{counter!r}")
        here = len(decidable(family))
        if row["decidable_pairs"] != here:
            problems.append(f"{family}: proposed {row['decidable_pairs']} decidable pairs, "
                            f"fixtures now give {here}")
    return {
        "status": "MATCHES_PROPOSAL" if not problems else "DRIFTED",
        "problems": problems,
        "artifact": PROPOSAL_ARTIFACT.name,
    }


def report() -> dict[str, Any]:
    """The admission, its membership with live counts, and the verification. The whole artifact."""
    members = []
    for family, counter in MEMBERS.items():
        pairs = admitted_families()[family]
        deciding = decidable(family)
        members.append({
            "family": family,
            "a_priori_counter": counter,
            "groups": len(pairs),
            "decidable": len(deciding),
            "structural_ties": list(STRUCTURAL_TIES.get(family, ())),
            "panel": PANEL_VERDICTS[family],
        })
    controls = []
    for family in (*CONTROLS, POSITIVE_CONTROL):
        pairs = control_families()[family]
        row: dict[str, Any] = {"family": family, "groups": len(pairs)}
        row["role"] = (
            "floor — both sides identical; separation here voids everything above it"
            if family == "placebo_identical" else
            "void — formatting only; recovery here is a layout reading and is VOID (§78.1)"
            if family == "rewhitespace_sham" else
            "positive — every instrument should preserve it; scored as preference, not counter"
        )
        if family == POSITIVE_CONTROL:
            rows = counter_deltas(family)
            row["counter_diagnostic"] = {
                "counter": A_PRIORI_COUNTER[family],
                "agreeing": sum(1 for r in rows if r["sign"] > 0),
                "groups": len(rows),
                "disagreeing_scenes": [r["scene"] for r in rows if r["sign"] < 0],
                "note": "a per-1k density on a lengthening edit can fall while the count rises",
            }
        controls.append(row)
    return {
        "admission": ADMISSION,
        "members": members,
        "controls": controls,
        "verification": verify_against_proposal(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = parser.parse_args(argv)

    payload = report()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if payload["verification"]["status"] != "DRIFTED" else 1

    print(f"B6 — {ADMISSION['decision']} by {ADMISSION['by']}, {ADMISSION['decided']}")
    print(f"  {ADMISSION['quote']}\n")
    print(f"  {'family':28s} {'counter':20s} {'decidable':>10s}  panel")
    for row in payload["members"]:
        panel = row["panel"]
        rate = "" if panel.get("rate") is None else f" {panel['rate']}"
        print(f"  {row['family']:28s} {row['a_priori_counter']:20s} "
              f"{row['decidable']:>4d}/{row['groups']:<5d}  {panel['read']}{rate} "
              f"({panel['where']})")
    print()
    for row in payload["controls"]:
        print(f"  {row['family']:28s} {row['groups']:>2d} pairs  {row['role']}")
        if "counter_diagnostic" in row:
            diag = row["counter_diagnostic"]
            print(f"  {'':28s}    counter {diag['counter']} agrees "
                  f"{diag['agreeing']}/{diag['groups']}, against "
                  f"{diag['disagreeing_scenes']} — {diag['note']}")
    verification = payload["verification"]
    print(f"\n  verification: {verification['status']}")
    for problem in verification.get("problems", []):
        print(f"    ! {problem}")
    return 1 if verification["status"] == "DRIFTED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
