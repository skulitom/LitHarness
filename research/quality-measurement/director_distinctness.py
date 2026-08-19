"""Are two directors two directors, or one director in hats?

**The check that has to pass before any comparison between directors is worth reporting**, and
it exists because this repo has measured the failure it guards against three times. §89.1:
`qwen3:14b` returned **one distinct answer vector across all four personas, byte-identical**, so
a panel that read as four judges was one judge replicated and 64 comparisons were 16 decisions.
§83: four simulated states of mind, one voice — the register was invariant to phenomenology.
§77: persona-to-passage sum-of-squares ratios of **0.0028, 0.0071 and 0.0342**, while changing
*the question* by one word moved a rate ten points. Personas in this project are usually
decorative, and `persona-reader-validity.md` §6 already carries the remedy for another
instrument: if shuffling the personas does not hurt, the personas are decorative.

**The comparison, stated before it runs.** Each director is asked for direction on the *same*
book state `DRAWS` times, varying only the sampler seed. The within-director spread is therefore
the generator's own noise; a between-director gap has to clear it to mean anything. Byte-identity
is checked first because it is free and because it is what actually happened.

**What a pass does and does not buy.** It buys the right to *ask* whether readers prefer one
director's book — nothing more. Whether they do is a reader question and waits with every other
reader question, and it is not free: §61 pre-registration (5) divides the confidence level of the
superiority claim by the candidate count, so **N directors divide §61's alpha by N**. At three
directors the headline is made at alpha/3, and §61's own sizing records what a thinner margin
costs. That price is printed by this module rather than discovered afterwards.

Local, deterministic, no quota unless `--wiring` is passed. Runs under `uv run python`.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

from litharness.domain.directors import (  # noqa: E402
    BUILTIN,
    DISTINCTNESS_FLOOR,
    Distinctness,
    distinctness,
)

RESULTS = HERE / "results"

#: Draws per director. Three is `DISTINCTNESS_FLOOR` — two draws give one within-director
#: distance, and a comparison against a single number is not a comparison.
DRAWS = DISTINCTNESS_FLOOR

PRE_REGISTRATION: dict[str, Any] = {
    "written": (
        "2026-08-19, before any director was drawn from and before any distance was computed"
    ),
    "question": (
        "Do two director personalities produce different direction, or is the brief inert?"
    ),
    "design": (
        f"Each director answers on the SAME book state {DRAWS} times, varying only the sampler "
        "seed. Within-director spread is the generator's noise; between-director distance must "
        "clear it."
    ),
    "statistic": (
        "Mean pairwise normalised compression distance, `domain/craft.py`'s measure, reused "
        "rather than invented because this project has refuted enough hand-rolled text "
        "distances to be suspicious of a new one."
    ),
    "reads": [
        "IDENTICAL — byte-identical directive sets. One director in costumes (§89.1's "
        "measured failure), and the comparison stops here.",
        "INDISTINCT — between-director distance <= within. The brief is decorative.",
        "DISTINCT — between > within, with a within-director noise floor above zero. The "
        "personalities clear the generator's own wobble.",
        "DISTINCT_NO_FLOOR — the sets differ and the within-director floor was ZERO, so the "
        "gap cleared nothing. It establishes that the briefs are not inert and not that the "
        "difference is large: with no wobble, 'between exceeds within' is satisfied by one "
        "differing character. A deterministic generator always reads this way.",
        f"UNREADABLE — fewer than {DRAWS} draws. Says so rather than passing.",
    ],
    "rail": (
        "A comparison between directors may not be reported until they read DISTINCT. Anything "
        "else is comparing one director against itself and reporting the seed."
    ),
    "price_of_a_pass": (
        "§61 pre-registration (5) divides the confidence level by the candidate-book count, so "
        "N directors divide §61's alpha by N. This is payable and it is payable in the currency "
        "the project is shortest of."
    ),
    "not_claimed": (
        "A DISTINCT reading says two directors write differently. It says nothing about whether "
        "either writes a better book — that is a reader question, and no arrangement of these "
        "numbers answers it."
    ),
}


def alpha_cost(directors: int, base_alpha: float = 0.05) -> dict[str, Any]:
    """What running this many directors costs §61's headline, computed rather than waved at."""
    divided = base_alpha / max(directors, 1)
    return {
        "directors": directors,
        "base_alpha": base_alpha,
        # Unrounded on purpose. A rounded alpha in a results file is a number somebody will
        # later compare against an exact one and find a discrepancy in; the rounding belongs in
        # the sentence a human reads, not in the record.
        "divided_alpha": divided,
        "note": (
            f"reporting the best of {directors} candidate books makes the superiority claim at "
            f"alpha {divided:.4f} rather than {base_alpha}, per §61 pre-registration (5)"
        ),
    }


def report(sets: dict[str, list[str]]) -> dict[str, Any]:
    """Every pair of directors, read against the rail, with the price attached."""
    names = sorted(sets)
    pairs: list[dict[str, Any]] = []
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            reading = distinctness(sets[left], sets[right])
            pairs.append(
                {
                    "left": left,
                    "right": right,
                    "reading": reading.reading.value,
                    "within": None if reading.within is None else round(reading.within, 4),
                    "between": None if reading.between is None else round(reading.between, 4),
                    "draws": reading.draws,
                    "comparable": reading.comparable,
                }
            )
    every_pair_distinct = bool(pairs) and all(row["comparable"] for row in pairs)
    return {
        "pre_registration": PRE_REGISTRATION,
        "directors": names,
        "pairs": pairs,
        "verdict": "COMPARABLE" if every_pair_distinct else "NOT_COMPARABLE",
        "alpha_cost": alpha_cost(len(names)),
    }


# --------------------------------------------------------------------------- the wiring pilot


def _cli(database: Path, *args: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["LITHARNESS_ENV"] = "test"
    environment["LITHARNESS_FAKE_PAD_CHARS"] = "600"
    return subprocess.run(
        [sys.executable, "-m", "litharness", "--database", str(database), *args],
        capture_output=True, text=True, cwd=str(REPO), env=environment, check=False,
    )


def wiring_run(names: list[str], scenes: int) -> dict[str, Any]:
    """Drive each director through the real loop and collect the direction it wrote.

    **A wiring pilot, not a test.** It runs on the padded fake provider, whose answers are a
    hash of the request — so it can show that each director's *request* differs and that the
    directives land authored and bounded, and it cannot show that a real model's personality is
    anything but decorative. That is exactly the question `--wiring` is unable to answer, and
    saying so here is cheaper than having somebody quote its number later.
    """
    from litharness.adapters.sqlite_store import SqliteStore

    sets: dict[str, list[str]] = {}
    with tempfile.TemporaryDirectory() as workspace:
        for name in names:
            bodies: list[str] = []
            for draw in range(DRAWS):
                database = Path(workspace) / f"{name}-{draw}.db"
                _cli(database, "init")
                _cli(
                    database, "new", f"The Toll Road {draw}",
                    "--premise", "A debtor works off an impossible debt.",
                    "--scenes", str(scenes),
                )
                _cli(database, "directors", "--register", name)
                for _ in range(4):
                    result = _cli(database, "--director", name, "tick")
                    if "no_work" in result.stdout:
                        break
                store = SqliteStore.open(database)
                try:
                    branches = store.branches()
                    if branches:
                        book, branch, _head = branches[0]
                        bodies.extend(
                            directive.body
                            for directive in store.machine_directives(book, branch)
                        )
                finally:
                    store.close()
            sets[name] = bodies
    out = report(sets)
    out["kind"] = (
        "wiring pilot, not a test: the padded fake provider answers by request digest, so a "
        "DISTINCT reading here is a fact about the prompts and not about any personality"
    )
    out["draws_collected"] = {name: len(bodies) for name, bodies in sets.items()}
    if any(row["reading"] == Distinctness.DISTINCT_NO_FLOOR.value for row in out["pairs"]):
        out["floor_warning"] = (
            "At least one pair read DISTINCT_NO_FLOOR: every draw from a director came back "
            "byte-identical to its siblings, so the between-director gap cleared a floor of "
            "zero. Expected here — the fake provider answers by request digest and this "
            "pilot's requests do not vary across draws — and it means the comparison was not "
            "tested against noise. A real generator at nonzero temperature is what makes this "
            "reading DISTINCT instead."
        )
    return out


# --------------------------------------------------------------------------- selftest


def selftest() -> int:
    failures: list[str] = []

    def check(claim: str, ok: bool) -> None:
        if not ok:
            failures.append(claim)

    same = ["down", "deeper", "lower"]
    check(
        "byte-identical sets read IDENTICAL, which is §89.1's measured failure",
        distinctness(same, list(same)).reading is Distinctness.IDENTICAL,
    )
    check(
        "two draws are UNREADABLE rather than passing",
        distinctness(["a", "b"], ["c", "d"]).reading is Distinctness.UNREADABLE,
    )
    left = ["under the road for the light", "under the road for the rope",
            "under the road for the maps"]
    right = ["the creditor at the door speaking", "the creditor at the door calling",
             "the creditor at the door reading"]
    check(
        "directors that differ more than they wobble read DISTINCT",
        distinctness(left, right).reading is Distinctness.DISTINCT,
    )
    check(
        "a deterministic generator reads DISTINCT_NO_FLOOR rather than DISTINCT, so a control "
        "that could not fail is never quoted as one that did (§50)",
        distinctness(["a", "a", "a"], ["bbbb", "bbbb", "bbbb"]).reading
        is Distinctness.DISTINCT_NO_FLOOR,
    )
    rolled = report({"a": left, "b": right})
    check("and a fully DISTINCT set is COMPARABLE", rolled["verdict"] == "COMPARABLE")
    check(
        "an IDENTICAL pair makes the whole set NOT_COMPARABLE",
        report({"a": same, "b": list(same)})["verdict"] == "NOT_COMPARABLE",
    )
    check(
        "three directors divide §61's alpha by three",
        abs(alpha_cost(3)["divided_alpha"] - 0.05 / 3) < 1e-9,
    )
    check(
        "and one director costs nothing, which is the control arm",
        alpha_cost(1)["divided_alpha"] == 0.05,
    )
    check(
        "the pre-registration prices the pass rather than only celebrating it",
        "price_of_a_pass" in PRE_REGISTRATION,
    )
    check(
        "and refuses the reading a DISTINCT result invites",
        "not_claimed" in PRE_REGISTRATION,
    )

    for line in failures:
        print(f"FAIL  {line}")
    print(f"selftest: {'PASS' if not failures else 'FAIL'} ({len(failures)} failure(s))")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--plan", action="store_true", help="print the pre-registration and stop")
    parser.add_argument(
        "--wiring", action="store_true", help="drive the real loop on the fake provider"
    )
    parser.add_argument("--scenes", type=int, default=6)
    parser.add_argument(
        "--director", action="append", default=None, help="repeatable; defaults to all built-ins"
    )
    parser.add_argument("--out", type=Path, default=RESULTS / "director-distinctness.json")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    names = args.director or sorted(BUILTIN)
    if args.plan or not args.wiring:
        print(json.dumps(PRE_REGISTRATION, indent=2))
        print(json.dumps(alpha_cost(len(names)), indent=2))
        return 0

    rolled = wiring_run(names, args.scenes)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rolled, indent=2), encoding="utf-8")
    for row in rolled["pairs"]:
        print(
            f"{row['left']:<12} vs {row['right']:<12} {row['reading']:<12} "
            f"within {row['within']} between {row['between']} draws {row['draws']}"
        )
    print(f"verdict: {rolled['verdict']}")
    if rolled.get("floor_warning"):
        print(f"WARNING: {rolled['floor_warning']}")
    print(f"alpha cost: {rolled['alpha_cost']['note']}")
    print(f"\n{rolled['kind']}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
