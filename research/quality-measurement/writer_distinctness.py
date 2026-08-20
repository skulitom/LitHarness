"""G1 for the Writer roster: are ten writers ten writers, or one writer in ten hats?

`plan/writer-roster.md` R2 and §6. Built the way `director_distinctness.py` is built and
comparing **drafts** rather than directives, because a Writer emits prose and a Director emits
direction — that is the whole difference between the two roles.

**The failure this guards against has been measured three times.** §89.1: `qwen3:14b` returned
one distinct answer vector across four personas, byte-identical. §83: four simulated states of
mind, one voice. §77: persona-to-passage sum-of-squares ratios of 0.0028, 0.0071 and 0.0342 while
changing *the question* by one word moved a rate ten points. A roster that has not passed this is
§89.1 in a fourth costume, and every comparison built on it would be a report about the seed.

**Two readings in one run** (operator amendment, 2026-08-20 — the control was originally at G2
and moved here, because distinctness without shuffle-sensitivity is decorative):

* **distinctness** — do two writers differ from each other more than each differs from itself?
* **the shuffle control** — does the prose track what the dossier *says*, or only the words it
  happens to contain?

**The literal form of the shuffle control is vacuous here, and that is worth writing down rather
than discovering after a run.** `plan/writer-roster.md` §6 said "shuffle the dossiers across the
roster". A Writer *is* its dossier: `Writer.render()` returns the dossier and nothing else, so
name and interests never reach the model. Permuting dossiers between writer names therefore
permutes labels over an identical set of requests — every pairwise reading comes back bit-for-bit
what it was, and a control that cannot fail is not a control (§50).

So the control implemented here scrambles **each dossier's own sentence order**, holding its
vocabulary and length exactly fixed, and compares each writer against its scrambled twin. It is
F3's shuffled-context arm in a different unit: same provenance, destroyed order. What it can
establish:

    twin distance <= within-writer floor   the model is reading the dossier's VOCABULARY;
                                           order carries nothing, and "deep in domain" is a
                                           bag of nouns
    twin distance >  within-writer floor   what the dossier says survives being said in a
                                           different order

Neither reading licenses a comparison between writers. That is what `distinctness` is for, and
both have to clear before anything downstream may be reported.

Runs against a local model through `elicit.Elicitor`, which already carries the replay cache, the
ollama transport and the thermal governor — reused rather than reimplemented for the reason every
module in this directory reuses them: an arm with its own transport is an arm whose numbers
cannot be compared with another arm's.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

from litharness.application.planner import render_prompt  # noqa: E402
from litharness.domain import writers  # noqa: E402
from litharness.domain.beats import SIX_BEAT, Beat  # noqa: E402
from litharness.domain.context import ContextPacket  # noqa: E402
from litharness.domain.directors import (  # noqa: E402
    DISTINCTNESS_FLOOR,
    Distinctness,
    distinctness,
)

RESULTS = HERE / "results"

#: Draws per writer. `DISTINCTNESS_FLOOR` is three: two draws give one within-writer distance,
#: and a comparison against a single number is not a comparison.
DRAWS = DISTINCTNESS_FLOOR

#: Words asked of each draft. Long enough that a dossier has somewhere to show up and short
#: enough that ten writers times two arms times three draws is affordable on one card.
TARGET_WORDS = 400

PRE_REGISTRATION: dict[str, Any] = {
    "gate": "G1 distinctness, with the shuffle control in the same run",
    "design": "plan/writer-roster.md R2, §6",
    "written": "2026-08-20, before any draft was drawn and before any distance was computed",
    "question": "Do ten dossiers produce ten writers, and does the prose track what a dossier "
                "says rather than the words it contains?",
    "draws_per_writer": DRAWS,
    "varying": "the sampler seed only; the beat, the packet and the target length are identical "
               "across every draw and every writer",
    "statistic": "mean pairwise normalised compression distance, `domain/craft.py`'s measure, "
                 "reused rather than invented because this project has refuted enough "
                 "hand-rolled text distances to be suspicious of a new one",
    "reads": [
        "IDENTICAL — byte-identical draft sets. One writer in costumes (§89.1's measured "
        "failure), and the comparison stops here.",
        "INDISTINCT — between-writer distance <= within. The dossier is decorative.",
        "DISTINCT — between > within with a within-writer floor above zero.",
        "DISTINCT_NO_FLOOR — the sets differ and the within-writer floor was ZERO, so the gap "
        "cleared nothing. It matters more here than for directors: a temperature-0 model makes "
        "within-writer distance zero and 'between exceeds within' is then satisfied by a single "
        "differing character.",
        f"UNREADABLE — fewer than {DRAWS} draws.",
    ],
    "shuffle_control": {
        "implemented": "each dossier's own sentence order is scrambled, vocabulary and length "
                       "held exactly fixed, and each writer is compared against its scrambled "
                       "twin. F3's shuffled-context arm in a different unit.",
        "not_implemented_and_why": "permuting dossiers ACROSS the roster is vacuous. A Writer "
                                   "is its dossier — `render()` returns the dossier and nothing "
                                   "else — so permuting between names permutes labels over an "
                                   "identical set of requests and every reading returns "
                                   "unchanged. A control that cannot fail is not a control "
                                   "(§50).",
        "reads": "twin distance at or below the within-writer floor means the model is reading "
                 "the dossier's vocabulary and not what it says",
    },
    "rail": "No comparison between writers may be reported until every pair reads DISTINCT or "
            "DISTINCT_NO_FLOOR **and** the shuffle control clears the floor.",
    "not_claimed": "A pass says ten dossiers write differently. It says nothing about whether "
                   "any of them writes a better book — that is a reader question, and no "
                   "arrangement of these numbers answers it.",
    "price_of_a_pass": "§61 pre-registration (5) divides the confidence level by the "
                       "candidate-book count. N directors x M writers is N*M candidate books "
                       "(writer-roster.md R4), and §96.1 makes the component grid multiplicative "
                       "on top of that.",
}


def _beat() -> Beat:
    return Beat(
        logical_id="s1",
        ordinal=1,
        of_total=30,
        title="The Archive",
        function="setup",
        template_id=SIX_BEAT.template_id,
        story_order_key="s1",
    )


def _packet() -> ContextPacket:
    return ContextPacket(
        query_id="beat:s1",
        target_logical_id="s1",
        book_id="bk",
        branch_id="br",
        base_revision_id="rev",
    )


def scramble_dossier(dossier: str) -> str:
    """The same sentences in a destroyed order. Vocabulary and length held exactly fixed.

    Deterministic — seeded from the dossier's own text — for `surprisal`'s reason: a random
    order would make the control non-deterministic and its own re-runs incomparable.

    A dossier that scrambles to itself is not a control, it is a placebo wearing a control's
    name, so the caller checks and skips. With four or more sentences that is vanishingly
    unlikely; with one it is certain.
    """
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", dossier.strip()) if s]
    if len(sentences) < 2:
        return dossier
    rng = random.Random(f"scramble|{dossier}")
    order = list(sentences)
    rng.shuffle(order)
    return " ".join(order)


def prompts_for(writer: writers.Writer | None) -> tuple[str, str]:
    return render_prompt(
        _beat(),
        book_title="The Toll Road",
        packet=_packet(),
        target_words=TARGET_WORDS,
        writer=writer,
    )


def draw(elicitor: Any, writer: writers.Writer | None, label: str) -> list[str]:
    """`DRAWS` continuations at one identical prompt, varying only the sampler seed."""
    system, prompt = prompts_for(writer)
    out: list[str] = []
    for sample in range(DRAWS):
        answer = elicitor.ask_raw(
            system,
            [{"role": "user", "content": prompt}],
            schema=None,
            max_tokens=TARGET_WORDS * 3,
            tag={"arm": "writer_distinctness", "writer": label, "draw": sample},
            sample=sample,
        )
        text = (answer.get("text") or "").strip()
        if text:
            out.append(text)
    return out


def report(
    live: dict[str, list[str]], twins: dict[str, list[str]], anonymous: list[str]
) -> dict[str, Any]:
    """Every pair read against the rail, plus each writer against its scrambled twin."""
    names = sorted(live)
    pairs: list[dict[str, Any]] = []
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            reading = distinctness(live[left], live[right])
            pairs.append({
                "left": left, "right": right,
                "reading": reading.reading.value,
                "within": None if reading.within is None else round(reading.within, 4),
                "between": None if reading.between is None else round(reading.between, 4),
                "draws": reading.draws,
                "comparable": reading.comparable,
            })

    shuffle_rows: list[dict[str, Any]] = []
    for name in names:
        if name not in twins:
            continue
        reading = distinctness(live[name], twins[name])
        shuffle_rows.append({
            "writer": name,
            "reading": reading.reading.value,
            "within": None if reading.within is None else round(reading.within, 4),
            "twin_distance": None if reading.between is None else round(reading.between, 4),
            "order_carries_something": reading.comparable,
        })

    # A writer against the anonymous drafter. Not a rail — it is the floor G0 already
    # established in bytes, re-established here in prose, and a roster that fails it while
    # passing everything else would mean the dossier changed the request and not the output.
    against_anonymous = [
        {
            "writer": name,
            "reading": distinctness(live[name], anonymous).reading.value,
        }
        for name in names
    ] if anonymous else []

    every_pair = bool(pairs) and all(row["comparable"] for row in pairs)
    shuffle_clears = bool(shuffle_rows) and all(
        row["order_carries_something"] for row in shuffle_rows
    )
    if not every_pair:
        verdict = "NOT_COMPARABLE"
    elif not shuffle_clears:
        # Distinct and shuffle-insensitive: the dossiers are not inert, and what they bind is
        # vocabulary rather than content. That is a real finding and it is not a pass.
        verdict = "DISTINCT_BUT_ORDER_BLIND"
    else:
        verdict = "COMPARABLE"
    return {
        "pre_registration": PRE_REGISTRATION,
        "writers": names,
        "pairs": pairs,
        "shuffle_control": shuffle_rows,
        "against_anonymous_drafter": against_anonymous,
        "every_pair_distinct": every_pair,
        "shuffle_control_clears": shuffle_clears,
        "verdict": verdict,
    }


def selftest() -> int:
    """No model. Checks the wiring and the control's own construction."""
    failures: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            failures.append(message)

    for writer in writers.BUILTIN.values():
        scrambled = scramble_dossier(writer.dossier)
        check(scrambled != writer.dossier, f"{writer.name}: scramble was a no-op")
        check(
            sorted(scrambled.split()) == sorted(writer.dossier.split()),
            f"{writer.name}: scramble changed the vocabulary",
        )
        check(
            scramble_dossier(writer.dossier) == scrambled,
            f"{writer.name}: scramble is not deterministic",
        )
        # A scrambled dossier must still be a legal one, or the control cannot be minted.
        writers.legal_dossier(scrambled)

    # The permute-across-roster form really is vacuous, and the selftest pins it rather than
    # leaving the claim in a docstring: permuting dossiers between names yields the same
    # request set, so the identical prompts come back.
    live = {name: prompts_for(w)[0] for name, w in writers.BUILTIN.items()}
    names = sorted(writers.BUILTIN)
    permuted = {
        names[i]: prompts_for(writers.BUILTIN[names[(i + 1) % len(names)]])[0]
        for i in range(len(names))
    }
    check(
        set(live.values()) == set(permuted.values()),
        "permuting dossiers across names changed the request set; the vacuity claim is wrong",
    )

    # Constructed sets, so the readings are exercised without a model.
    a = ["alpha beta gamma delta", "alpha beta gamma epsilon", "alpha beta gamma zeta"]
    b = ["omega psi chi phi", "omega psi chi upsilon", "omega psi chi tau"]
    check(distinctness(a, b).reading is Distinctness.DISTINCT, "constructed sets must be DISTINCT")
    check(
        distinctness(a, list(a)).reading is Distinctness.IDENTICAL,
        "a set against itself must be IDENTICAL",
    )
    check(distinctness(a[:1], b[:1]).reading is Distinctness.UNREADABLE, "one draw is UNREADABLE")

    built = report({"x": a, "y": b}, {}, [])
    check(built["verdict"] == "DISTINCT_BUT_ORDER_BLIND",
          f"an empty shuffle control must not read COMPARABLE, got {built['verdict']}")

    for message in failures:
        print(f"FAIL {message}")
    print(f"writer_distinctness selftest: {len(failures)} failures")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--model", default="gemma3:12b", help="local model, through ollama")
    parser.add_argument("--out", default=str(RESULTS / "writer-g1.json"))
    parser.add_argument("--cache", default=str(HERE / "derived" / "writer-g1.jsonl"))
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()

    from elicit import Elicitor

    Path(args.cache).parent.mkdir(parents=True, exist_ok=True)
    elicitor = Elicitor(
        Path(args.cache), model=args.model, spot_model=None, transport="ollama", no_think=True
    )
    roster = writers.BUILTIN
    live = {name: draw(elicitor, w, name) for name, w in roster.items()}
    twins: dict[str, list[str]] = {}
    for name, writer in roster.items():
        scrambled = scramble_dossier(writer.dossier)
        if scrambled == writer.dossier:
            continue
        twin = writers.build(f"{name}-scrambled", scrambled, interests=writer.interests)
        twins[name] = draw(elicitor, twin, f"{name}-scrambled")
    anonymous = draw(elicitor, None, "anonymous")

    built = report(live, twins, anonymous)
    built["model"] = args.model
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(built, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({k: built[k] for k in ("verdict", "every_pair_distinct",
                                            "shuffle_control_clears")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
