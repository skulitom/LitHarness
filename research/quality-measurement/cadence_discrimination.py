"""W3: is "a cadence a reader can feel" something a reader can feel?

PLAN.md §1a.3 item 3 asks for promises paid "on a cadence a reader can feel". **Nothing in
this project has measured whether that cadence is perceptible at all**, and the sentence has
been carried as a goal since before there was an instrument. This module asks the question
before anybody builds a cadence detector, because a detector for an imperceptible property is
the twenty-second refuted proxy (`BRIEF.md` §2) and would cost more to remove than to skip.

**The report channel and no other.** §89 measured the verdict channel weighting position over
text roughly 4,676x; E1/E2 (prefer a side) are VOID and E6 — *name the single most salient
difference* — survives. So this study asks E6's byte-frozen question, imported from
`domain/discrimination.py` rather than restated, and **has no preference leg at all**. A
version of this study that asked which cadence the reader preferred would be measuring
position.

**The manipulation is certified by construction, which is the part that is usually hard.**
Three variants of one span carry the **same payoff sentences in the same order** and differ
only in *where those sentences sit*: spread evenly, clustered early with a starved tail, or
withheld until a terminal dump. Word count is identical to the character, the inserted text is
identical as a set, and the only difference is placement — so a response naming a placement
difference is naming cadence and cannot be naming length, vocabulary or subject.

That is `paragraph_shuffle`'s certification (the same paragraphs, reordered) applied to a
designed insert set, and inserting authored clauses into own prose is `filler_inject`'s
existing practice rather than a new liberty. What it costs is stated: the payoff sentences are
authored and generic, so this measures whether *explicit, evenly-marked* payoff placement is
nameable — not whether a subtly-paced book reads differently from a lumpy one. A null here
therefore bounds the easier question, and a null on the easier question is the more informative
of the two.

**The bar is the measured null, never a nominal rate**, and both controls ride every batch:

    cadence arm      the three cadence contrasts
    placebo          a variant against itself            -> the matcher must not fire
    whitespace sham  a variant against its own respacing -> the matcher must not fire

The verdict is `fisher_exact_greater` on the 2x2 of (cadence fires / cadence misses) against
(control fires / control misses), at `elicitation_study.FAMILY_ALPHA`. A matcher for a topic
fires at whatever rate that vocabulary appears unprompted, and that rate is estimated from the
same run rather than assumed — E6's own discipline, copied because it is the reason E6's
numbers mean anything.

**The null is a result.** If cadence is not nameable, W3 stops here: no detector, no candidate
axis, and the null is written to `results/` and to one paragraph in
`plan/promise-payoff-development.md` §7.

    uv run python research/quality-measurement/cadence_discrimination.py --selftest
    uv run python research/quality-measurement/cadence_discrimination.py --dry-run
    uv run python research/quality-measurement/cadence_discrimination.py --model qwen3:14b --yes
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ablate  # noqa: E402
from elicit import Elicitor  # noqa: E402
from elicitation_study import FAMILY_ALPHA, fisher_exact_greater  # noqa: E402

RESULTS = HERE / "results"
SCENES = HERE / "corpora" / "toll-scenes.json"

#: Scenes per span. Two scenes is roughly 2,000 words, which is long enough for four payoff
#: placements to be distinguishable and short enough that both sides fit one prompt — E6 shows
#: the model two passages, so the span is bounded by the ask rather than by the corpus.
SCENES_PER_SPAN = 2

#: Payoff sentences inserted per span. Four gives three distinguishable distributions over a
#: span; three would make "front-loaded" and "even" nearly the same arrangement.
INSERTS = 4

#: Where each variant places its inserts, as fractions of the span's paragraph count. The same
#: sentences in the same order in all three; only these fractions differ, which is the whole
#: manipulation and the whole of what a response has to name.
CADENCES: dict[str, tuple[float, ...]] = {
    "even": (0.20, 0.40, 0.60, 0.80),
    "front_loaded": (0.08, 0.16, 0.24, 0.32),
    "starved_dumped": (0.72, 0.80, 0.88, 0.96),
}

#: The payoff sentences. Deliberately generic, deliberately about *settling something that was
#: outstanding*, and deliberately carrying no proper noun — a payoff naming a character would
#: land as a continuity edit in one position and a contradiction in another, and the
#: manipulation would then be about coherence rather than about placement.
#:
#: Frozen with the matcher below: these are the content whose *placement* is under test, so
#: editing one is a different manipulation.
PAYOFFS: tuple[str, ...] = (
    "The question that had been hanging since the first morning finally had its answer, "
    "and the answer cost something.",
    "What had been promised at the gate was made good, in full and in front of witnesses.",
    "The debt that everyone had been pretending not to count was counted, out loud.",
    "The thing that had been set aside to deal with later was dealt with, and it stayed dealt "
    "with.",
)

#: **Committed before any response exists**, and this is the whole reason it is written here
#: rather than derived from the answers. E6 is scored by a matcher, so the matcher *is* the
#: rubric; one drafted after reading responses is fitted to its own answers, which is what
#: freezing `AXIS_MATCHERS` exists to prevent one module over.
#:
#: Generous about vocabulary, strict about topic — `AXIS_MATCHERS`' rule. A model that says
#: "one resolves things throughout and the other saves it all for the end" and one that says
#: "the pacing of the payoffs differs" should both count; a model that says "one is more
#: descriptive" should not.
CADENCE_MATCHER = (
    r"\b(cadence|pacing|paced|pace\b|rhythm|tempo|spread out|spaced|interval|"
    r"front[- ]?load|back[- ]?load|early on|toward the end|at the end|throughout|"
    r"distribut|cluster|bunch|timing|when (?:the |these |those )?(?:payoff|resolution|"
    r"answer|revelation)|order (?:of|in which)|sequence|resolv\w* (?:early|late|throughout)|"
    r"payoff|pay[- ]?off|resolution|closure|answered|settled|ties? up|wrap(?:ped|s)? up)\w*"
)

_CADENCE = re.compile(CADENCE_MATCHER, re.IGNORECASE)

#: **A diagnostic matcher, written after the first run and labelled as such**, in the position
#: `latent_probe`'s `p0_best_single_DIAGNOSTIC` occupies: it is in no bar, no verdict turns on
#: it, and it exists because the first run's answers said something the pre-registration had no
#: field for.
#:
#: What they said was that one passage "includes additional details" the other "omits" — about
#: two passages whose word multisets, character counts and paragraph counts are identical by
#: construction and asserted by `certify`. Nothing is omitted from either. So at this passage
#: length the report channel appears to read a *displacement* of four sentences as a *deletion*,
#: and the byte-identical placebo cannot catch that: shown two identical passages the model
#: correctly says identical, so the control clears while the failure is live one step away.
#:
#: Reported as a rate beside the verdict, never folded into it. Turning this into a bar would be
#: fitting a rubric to the answers that produced it, which is the whole reason `CADENCE_MATCHER`
#: is frozen above.
OMISSION_MATCHER = (
    r"\b(omit\w*|missing|absent|lacks?|leaves? out|left out|excludes?|"
    r"additional (?:details?|content|narrative)|more (?:details?|content)|"
    r"condensed|shorter|truncat\w*|abridg\w*|full(?:er)? (?:narrative|account|version))\b"
)

_OMISSION = re.compile(OMISSION_MATCHER, re.IGNORECASE)


def claims_omission(said: str | None) -> bool:
    """Did this response claim one passage contains text the other does not? Diagnostic only."""
    return bool(said and _OMISSION.search(said))

#: Refuse above this many calls without `--yes`.
CALL_GUARD = 600


def names_cadence(said: str | None) -> bool:
    """Did this response name a cadence property? Deterministic; the matcher is frozen."""
    return bool(said and _CADENCE.search(said))


@dataclass(frozen=True, slots=True)
class Pair:
    """One E6 contrast, with the arm it belongs to."""

    pair_id: str
    arm: str
    left: str
    right: str


def spans(scenes: list[str], *, per_span: int = SCENES_PER_SPAN) -> list[str]:
    """Disjoint spans of `per_span` consecutive scenes. Disjoint, because overlapping spans
    would put the same prose on both sides of a cluster and inflate every count over it."""
    return [
        "\n\n".join(scenes[index : index + per_span])
        for index in range(0, len(scenes) - per_span + 1, per_span)
    ]


def place(span: str, fractions: tuple[float, ...]) -> str:
    """Insert `PAYOFFS` into `span` at the given fractional paragraph positions.

    Each insert becomes its own paragraph, so no sentence of the original is edited and the
    span's own prose is byte-identical across all three variants. Positions are clamped to
    distinct paragraph boundaries — two inserts landing on the same boundary would silently make
    a four-payoff cadence a three-payoff one in that variant only, which is the manipulation
    quietly differing from its own declaration.
    """
    blocks = ablate.paragraphs(span)
    if not blocks:
        return span
    taken: set[int] = set()
    positions: list[int] = []
    for fraction in fractions[:INSERTS]:
        index = min(max(round(fraction * len(blocks)), 0), len(blocks))
        while index in taken:
            index += 1
            if index > len(blocks):
                index = 0
        taken.add(index)
        positions.append(index)
    out: list[str] = []
    for position, block in enumerate(blocks):
        for slot, index in enumerate(positions):
            if index == position:
                out.append(PAYOFFS[slot])
        out.append(block)
    for slot, index in enumerate(positions):
        if index >= len(blocks):
            out.append(PAYOFFS[slot])
    return "\n\n".join(out)


def build_pairs(spans_: list[str]) -> list[Pair]:
    """The cadence contrasts and both controls, over every span.

    Three cadence contrasts per span rather than one: even-vs-front, even-vs-dumped and
    front-vs-dumped are three different questions about placement, and reporting only the
    easiest of them would be choosing the arm after seeing the material.
    """
    pairs: list[Pair] = []
    contrasts = (
        ("even", "front_loaded"),
        ("even", "starved_dumped"),
        ("front_loaded", "starved_dumped"),
    )
    for index, span in enumerate(spans_):
        variants = {name: place(span, fractions) for name, fractions in CADENCES.items()}
        for left, right in contrasts:
            pairs.append(
                Pair(f"cadence-{index}-{left}-vs-{right}", "cadence",
                     variants[left], variants[right])
            )
        even = variants["even"]
        pairs.append(Pair(f"placebo-{index}", "placebo", even, even))
        pairs.append(
            Pair(f"sham-{index}", "sham", even, ablate.rewhitespace(even, 1.0))
        )
    return pairs


def certify(spans_: list[str]) -> list[str]:
    """Faults in the manipulation's own premise, empty when it holds.

    **A sham whose premise is unverified is a control that cannot fail**, and §90 records that
    exact objection as the reason a paraphrase sham was designed and not built. The premise here
    is checkable, so it is checked: the three variants of a span must have identical word
    multisets, identical lengths, and genuinely different arrangements. If any of that stops
    being true, this study is measuring something other than placement and says so loudly rather
    than reporting a rate.
    """
    faults: list[str] = []
    for index, span in enumerate(spans_):
        variants = {name: place(span, fractions) for name, fractions in CADENCES.items()}
        words = {name: sorted(text.split()) for name, text in variants.items()}
        first = next(iter(words.values()))
        if any(other != first for other in words.values()):
            faults.append(f"span {index}: the variants do not carry identical words")
        if len({text for text in variants.values()}) != len(variants):
            faults.append(f"span {index}: two cadence variants are byte-identical")
        for name, text in variants.items():
            if sum(text.count(payoff) for payoff in PAYOFFS) != INSERTS:
                faults.append(f"span {index}/{name}: not all {INSERTS} payoffs are present once")
    return faults


def ask(
    elicitor: Elicitor, pair: Pair, *, orientation: int, model: str
) -> dict[str, Any]:
    """One E6 presentation, in one orientation. The question is imported, never restated."""
    from litharness.domain.discrimination import (
        ANSWER_MAX_TOKENS,
        E6_QUESTION,
        E6_SCHEMA,
    )

    left, right = (
        (pair.left, pair.right) if orientation == 0 else (pair.right, pair.left)
    )
    record = elicitor.ask_raw(
        "You are shown two passages and asked one question about them. Answer only the "
        "question, in one sentence, as a single JSON object.",
        [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"PASSAGE ONE:\n{left}\n\nPASSAGE TWO:\n{right}\n\n"
                        f"{E6_QUESTION}",
                    }
                ],
            }
        ],
        schema=E6_SCHEMA,
        max_tokens=ANSWER_MAX_TOKENS,
        tag={
            "pair": pair.pair_id,
            "arm": pair.arm,
            "stage": "cadence",
            "orientation": orientation,
        },
        sample=orientation,
        model=model,
    )
    said = ""
    if not record.get("refused") and record.get("text"):
        try:
            said = str(json.loads(record["text"]).get("difference", ""))
        except (json.JSONDecodeError, AttributeError):
            said = ""
    return {
        "pair": pair.pair_id,
        "arm": pair.arm,
        "orientation": orientation,
        "said": said,
        "refused": not said,
        "named_cadence": names_cadence(said),
        "claims_omission": claims_omission(said),
    }


def score(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The cadence rate against the measured null. Pure arithmetic over answered cells."""
    answered = [row for row in rows if not row["refused"]]
    by_arm: dict[str, list[dict[str, Any]]] = {}
    for row in answered:
        by_arm.setdefault(row["arm"], []).append(row)

    def rate(arm: str) -> tuple[int, int]:
        rows_ = by_arm.get(arm, [])
        return sum(1 for row in rows_ if row["named_cadence"]), len(rows_)

    fired, seen = rate("cadence")
    placebo_fired, placebo_seen = rate("placebo")
    sham_fired, sham_seen = rate("sham")
    null_fired = placebo_fired + sham_fired
    null_seen = placebo_seen + sham_seen

    # **Both controls must hold or the batch is VOID**, and holding means the matcher does not
    # fire on material that carries no cadence difference. A batch whose placebo names cadence
    # has a matcher firing on vocabulary rather than on placement, and its cadence rate is a
    # measurement of that matcher.
    controls_hold = placebo_fired == 0 and sham_fired == 0
    p = (
        fisher_exact_greater(fired, seen - fired, null_fired, null_seen - null_fired)
        if seen and null_seen
        else 1.0
    )
    if not (seen and null_seen):
        verdict = "UNREADABLE"
    elif not controls_hold:
        verdict = "VOID"
    elif p <= FAMILY_ALPHA:
        verdict = "NAMES_CADENCE"
    else:
        verdict = "DOES_NOT"
    # The post-hoc diagnostic (see `OMISSION_MATCHER`). In no bar, and reported per arm so the
    # placebo's rate sits beside the cadence arm's: the placebo is where the channel is known to
    # behave, and a gap between the two is the size of the artifact.
    omission = {
        arm: {
            "claims": sum(1 for row in rows_ if row.get("claims_omission")),
            "responses": len(rows_),
        }
        for arm, rows_ in sorted(by_arm.items())
    }
    return {
        "cadence": {"fired": fired, "responses": seen},
        "placebo": {"fired": placebo_fired, "responses": placebo_seen},
        "sham": {"fired": sham_fired, "responses": sham_seen},
        "null": {"fired": null_fired, "responses": null_seen},
        "cadence_rate": round(fired / seen, 4) if seen else None,
        "null_rate": round(null_fired / null_seen, 4) if null_seen else None,
        "fisher_p": round(p, 6),
        "alpha": FAMILY_ALPHA,
        "controls_hold": controls_hold,
        "verdict": verdict,
        "DIAGNOSTIC_omission_claims": omission,
        "DIAGNOSTIC_reading": (
            "post-hoc and in no bar: the cadence variants are word-identical by construction "
            "and asserted by `certify`, so every omission claim on that arm is false about the "
            "text; a gap between its rate and the placebo's is the size of the artifact"
        ),
        "reading": (
            "a NAMES_CADENCE verdict makes cadence a *nominated* axis and nothing more: "
            "`domain/axes.py`'s admission path still requires a deterministic counter, an "
            "E6-family validation on fresh pairs this corpus never touched, and a "
            "reader-established direction, before anything is emitted"
        ),
    }


def selftest() -> int:
    """The manipulation's premise and the matcher's behaviour, before a call is bought."""
    failures: list[str] = []
    payload = json.loads(SCENES.read_text(encoding="utf-8"))
    scenes = [str(scene["text"]) for scene in payload["scenes"]]
    spans_ = spans(scenes)
    if len(spans_) < 2:
        failures.append(f"{len(spans_)} span(s); the study needs at least two")
    for fault in certify(spans_):
        failures.append(fault)

    for phrase, expected in (
        ("One resolves things throughout and the other saves it all for the end.", True),
        ("The pacing of the payoffs differs between them.", True),
        ("Passage two clusters its revelations early.", True),
        ("One passage is more descriptive than the other.", False),
        ("Passage A uses double spaces after periods.", False),
        ("They are identical.", False),
    ):
        if names_cadence(phrase) is not expected:
            failures.append(f"the matcher read {phrase!r} as {not expected}")

    void = score(
        [
            {"arm": "cadence", "refused": False, "named_cadence": True, "pair": "p"},
            {"arm": "placebo", "refused": False, "named_cadence": True, "pair": "p"},
            {"arm": "sham", "refused": False, "named_cadence": False, "pair": "p"},
        ]
    )
    if void["verdict"] != "VOID":
        failures.append("a batch whose placebo named cadence was not VOID")
    clean = score(
        [{"arm": "cadence", "refused": False, "named_cadence": True, "pair": f"p{i}"}
         for i in range(20)]
        + [{"arm": "placebo", "refused": False, "named_cadence": False, "pair": f"q{i}"}
           for i in range(10)]
        + [{"arm": "sham", "refused": False, "named_cadence": False, "pair": f"r{i}"}
           for i in range(10)]
    )
    if clean["verdict"] != "NAMES_CADENCE":
        failures.append("a clean 20/20 against a 0/20 null did not clear the bar")
    flat = score(
        [{"arm": "cadence", "refused": False, "named_cadence": False, "pair": f"p{i}"}
         for i in range(20)]
        + [{"arm": "placebo", "refused": False, "named_cadence": False, "pair": f"q{i}"}
           for i in range(10)]
        + [{"arm": "sham", "refused": False, "named_cadence": False, "pair": f"r{i}"}
           for i in range(10)]
    )
    if flat["verdict"] != "DOES_NOT":
        failures.append("a matcher that never fired was not read as a null")
    if score([])["verdict"] != "UNREADABLE":
        failures.append("an empty batch produced a verdict")

    # **Attainability, I7's check, before the bar is committed.** With this many pairs, can the
    # bar be cleared at all? A Fisher test on a table this small can be exact-zero-power, which
    # is a declared bar naming a quantity that cannot reach it — the failure seven prior
    # declarations made.
    spans_count = max(len(spans_), 1)
    cadence_cells = spans_count * 3 * 2
    null_cells = spans_count * 2 * 2
    best = fisher_exact_greater(cadence_cells, 0, 0, null_cells)
    if best > FAMILY_ALPHA:
        failures.append(
            f"at {cadence_cells} cadence cells against {null_cells} null cells the best "
            f"attainable p is {best:.4f}, above alpha {FAMILY_ALPHA}; the bar cannot be cleared"
        )

    for line in failures:
        print(f"FAIL {line}", file=sys.stderr)
    print("selftest: " + ("FAILED" if failures else "passed"), file=sys.stderr)
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3:14b")
    parser.add_argument("--transport", default="ollama", choices=("ollama", "cli", "sdk"))
    parser.add_argument("--spans", type=int, default=None)
    parser.add_argument("--rest-ratio", type=float, default=1.0)
    parser.add_argument("--cache", default="cadence-raw.jsonl")
    parser.add_argument("--out", default="cadence-discrimination.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    payload = json.loads(SCENES.read_text(encoding="utf-8"))
    scenes = [str(scene["text"]) for scene in payload["scenes"]]
    spans_ = spans(scenes)
    if args.spans:
        spans_ = spans_[: args.spans]
    faults = certify(spans_)
    if faults:
        for fault in faults:
            print(f"PREMISE FAULT {fault}", file=sys.stderr)
        raise SystemExit(
            "the manipulation's own premise does not hold; a control whose premise is "
            "unverified is a control that cannot fail"
        )

    pairs = build_pairs(spans_)
    calls = len(pairs) * 2
    print(
        f"{len(spans_)} span(s), {len(pairs)} pair(s) x 2 orientation(s) = {calls} call(s) "
        f"on {args.model} via {args.transport}",
        file=sys.stderr,
    )
    if calls > CALL_GUARD and not args.yes:
        raise SystemExit(f"{calls} calls is above the {CALL_GUARD} guard; pass --yes")
    if not (args.yes or args.dry_run):
        raise SystemExit("pass --yes to spend, or --dry-run to exercise the arithmetic")

    rows: list[dict[str, Any]] = []
    with Elicitor(
        RESULTS / args.cache,
        model=args.model,
        spot_model=None,
        transport=args.transport,
        rest_ratio=args.rest_ratio,
        dry_run=args.dry_run,
    ) as elicitor:
        for pair in pairs:
            for orientation in (0, 1):
                rows.append(ask(elicitor, pair, orientation=orientation, model=args.model))
        spend = elicitor.spend()

    report = {
        "study": "cadence_discrimination",
        "pre_registration": {
            "channel": "report (E6), imported byte-for-byte from domain/discrimination.py",
            "no_preference_leg": True,
            "cadences": {name: list(f) for name, f in CADENCES.items()},
            "payoffs": list(PAYOFFS),
            "matcher": CADENCE_MATCHER,
            "alpha": FAMILY_ALPHA,
            "bar": "the measured null on the same matcher and the same pairs, never 0.5",
            "controls": "placebo and whitespace sham ride every batch; either firing VOIDs it",
        },
        "source": str(SCENES),
        "model": args.model,
        "transport": args.transport,
        "dry_run": bool(args.dry_run),
        "spans": len(spans_),
        "pairs": len(pairs),
        "spend": spend,
        **score(rows),
        "responses": rows,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / args.out).write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"cadence {report['cadence']['fired']}/{report['cadence']['responses']} "
        f"null {report['null']['fired']}/{report['null']['responses']} "
        f"p={report['fisher_p']} -> {report['verdict']}",
        file=sys.stderr,
    )
    print(f"wrote {RESULTS / args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
