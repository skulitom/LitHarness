"""W1's derivation run: what kinds of debt does the summariser actually report?

`domain/promises.PROMISE_KINDS` began as a five-way guess — plot, character, progression,
mystery, tone — and a guess is exactly how twenty-one refuted proxies entered this project
(`BRIEF.md` §2). So the set is **pruned against observation before it is frozen**, and this
module is that observation. It is deliberately not a study with a bar: nothing here is
falsified, nothing is promoted, and the output is a distribution plus the cuts a
pre-registered reading rule makes from it.

**Two arms, because one of them cannot nominate.** The shipped schema constrains `kind` to an
enum, so a model asked through it can only ever answer inside the candidate set — which
measures the *prune* and is blind to a category the taxonomy is missing. The `open` arm asks
the same question with the constraint removed and one word of the model's own choosing, and it
is the only arm from which a nomination can come. Running only the constrained arm would have
produced a tidy distribution over five categories and no way to discover a sixth, which is the
shape of error this project keeps recording.

**The reading rule is pre-registered in `plan/promise-payoff-development.md` §1.1 and copied
into the result file**, so it cannot be adjusted to suit the distribution once it is visible:

    zero reports                    -> CUT
    under MINOR_SHARE of reports    -> CUT, unless it is the only kind some promise got
    out-of-set at NOMINATE_SHARE+   -> NOMINATION, admitted only by an operator act
    per model, never pooled         -> two models' taxonomies averaged are neither model's

**Substrate.** Own-generated prose only, and for the reason BRIEF §2 Pass 6 gives rather than
for convenience: a model's familiarity with published text swings model-based measures further
than real damage does. `corpora/toll-scenes.json` is the committed export, so this module
survives a fresh clone; `--book-db` points at any book database instead.

Free legs first, both of which execute before a call is bought:

    uv run python research/quality-measurement/promise_kinds.py --selftest
    uv run python research/quality-measurement/promise_kinds.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, cast

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from corpus_io import Unit, generated_scenes  # noqa: E402
from elicit import Elicitor  # noqa: E402

RESULTS = HERE / "results"

#: The committed own-generated corpus. The *export*, not the gitignored database beside it, so
#: this module runs on a fresh clone where the §70 persona runs do not.
SCENES = HERE / "corpora" / "toll-scenes.json"

#: Below this share of reported promises a kind is cut. Five percent of a few dozen promises is
#: one or two reports, which is a category the corpus does not support rather than a rare one —
#: and the "unless it is somebody's only kind" clause is what keeps a genuinely narrow category
#: from being cut for being narrow.
MINOR_SHARE = 0.05

#: At or above this share of reported promises, an unregistered kind is worth an operator's
#: attention. Deliberately double the cut threshold: a nomination costs somebody a decision, and
#: a threshold equal to the cut would nominate every stray synonym.
NOMINATE_SHARE = 0.10

#: Answers per scene per arm. The datum is a distribution over categories, so the money belongs
#: in the sample count rather than the tier — but a taxonomy is a coarse thing and three draws
#: per scene is already more resolution than a five-way split can use.
SAMPLES = 3

#: Token headroom. The shipped prompt asks for ~60 words of prose plus a structured envelope.
MAX_TOKENS = 2_000

#: Refuse above this many calls without `--yes`. Two arms x scenes x samples; a derivation run
#: that needs a four-figure budget has stopped being a derivation run.
CALL_GUARD = 400


def load_scenes(book_db: str | None, *, limit: int | None) -> tuple[list[Unit], str]:
    """Own-generated scenes, and an honest label for where they came from."""
    if book_db:
        units = generated_scenes(book_db, min_words=1)
        source = book_db
    else:
        payload = json.loads(SCENES.read_text(encoding="utf-8"))
        units = [
            Unit(
                unit_id=str(scene["unit_id"]),
                source="generated",
                text=str(scene["text"]),
                position=index,
                work_id="toll",
            )
            for index, scene in enumerate(payload["scenes"], start=1)
        ]
        source = str(SCENES)
    return (units[:limit] if limit else units), source


def open_system(shipped: str, kinds: tuple[str, ...]) -> str:
    """The shipped summariser system prompt with the kind enumeration removed.

    **Derived by substitution and asserted rather than rewritten**, because an open arm written
    from scratch would differ from the shipped prompt in every other respect too, and then the
    two arms would not be measuring the same question asked two ways. If the shipped prompt
    stops containing the enumeration this raises, which is the loud failure — an "open" arm
    that silently kept naming the candidate set is an arm that cannot nominate while reporting
    that it can.
    """
    marker = f"({', '.join(kinds)})"
    if marker not in shipped:
        raise SystemExit(
            f"the shipped summary prompt no longer contains {marker!r}; the open arm is "
            "derived from it by substitution and cannot be built from a prompt that changed"
        )
    return shipped.replace(marker, "(one word of your own choosing)")


def open_schema(shipped: dict[str, Any]) -> dict[str, Any]:
    """The shipped schema with `kind`'s enum dropped and nothing else touched."""
    payload = cast(dict[str, Any], json.loads(json.dumps(shipped)))
    item = payload["properties"]["promises_opened"]["items"]["properties"]
    item["kind"] = {"anyOf": [{"type": "string"}, {"type": "null"}]}
    return payload


def reported_kinds(answer: dict[str, Any]) -> list[str | None]:
    """The `kind` of each opened promise in one answer, `None` where none was given.

    Normalised only by case and space. Mapping a near-miss onto a registered kind here would
    be this module deciding the taxonomy it exists to observe.
    """
    opened = answer.get("promises_opened")
    if not isinstance(opened, list):
        return []
    out: list[str | None] = []
    for item in opened:
        if not isinstance(item, dict):
            continue
        value = item.get("kind")
        out.append(value.strip().lower() if isinstance(value, str) and value.strip() else None)
    return out


def read_distribution(
    counts: Counter[str], *, candidates: tuple[str, ...], sole: set[str], total: int
) -> dict[str, Any]:
    """Apply the pre-registered rule to one model's observed distribution.

    Pure arithmetic over a counter, which is what makes `--selftest` able to prove the rule
    behaves before a call is bought. `total` is the number of *reported promises*, not the
    number of calls: a scene reporting three promises contributes three observations, because
    the question is what fraction of debts fall in each category.
    """
    kept: list[str] = []
    cut: list[dict[str, Any]] = []
    for kind in candidates:
        seen = counts.get(kind, 0)
        share = seen / total if total else 0.0
        if seen == 0:
            cut.append({"kind": kind, "reports": 0, "share": 0.0, "why": "never reported"})
        elif share < MINOR_SHARE and kind not in sole:
            cut.append(
                {
                    "kind": kind,
                    "reports": seen,
                    "share": round(share, 4),
                    "why": f"under {MINOR_SHARE:.0%} and never the only kind a promise got",
                }
            )
        else:
            kept.append(kind)
    nominations = [
        {"kind": kind, "reports": seen, "share": round(seen / total, 4)}
        for kind, seen in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
        if kind not in candidates and total and seen / total >= NOMINATE_SHARE
    ]
    unregistered = sorted(
        ({kind: seen for kind, seen in counts.items() if kind not in candidates}).items(),
        key=lambda pair: (-pair[1], pair[0]),
    )
    return {
        "reported_promises": total,
        "counts": dict(sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))),
        "keep": kept,
        "cut": cut,
        # Every unregistered answer, not only the ones clearing the nomination share: the tail
        # is the interesting half and a report that printed only what cleared a threshold would
        # be the silent-cap failure §89's rail refuses.
        "unregistered": [{"kind": kind, "reports": seen} for kind, seen in unregistered],
        "nominations": nominations,
    }


def summarise_once(
    elicitor: Elicitor,
    text: str,
    *,
    unit_id: str,
    sample: int,
    model: str,
    arm: str,
    system: str,
    prompt: str,
    schema: dict[str, Any],
) -> dict[str, Any] | None:
    """One call through a summariser prompt. `None` when nothing parseable came back."""
    record = elicitor.ask_raw(
        system,
        [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        schema=schema,
        max_tokens=MAX_TOKENS,
        tag={"unit": unit_id, "arm": arm, "stage": "summary_kind", "sample": sample},
        sample=sample,
        model=model,
    )
    if record.get("refused") or not record.get("text"):
        return None
    try:
        decoded = json.loads(record["text"])
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, dict) else None


def run(args: argparse.Namespace) -> dict[str, Any]:
    from litharness.application.summarize import SUMMARY_SCHEMA, render_summary_prompt
    from litharness.domain.promises import PROMISE_KINDS

    units, source = load_scenes(args.book_db, limit=args.scenes)
    if not units:
        raise SystemExit(f"no scenes in {source}")
    arms = ("constrained", "open")
    planned = len(units) * args.samples * len(arms)
    print(
        f"{len(units)} scene(s) from {source}; {len(arms)} arm(s) x {args.samples} sample(s) "
        f"= {planned} call(s) on {args.model}",
        file=sys.stderr,
    )
    if planned > CALL_GUARD and not args.yes:
        raise SystemExit(f"{planned} calls is above the {CALL_GUARD} guard; pass --yes")
    if not (args.yes or args.dry_run):
        raise SystemExit("pass --yes to spend, or --dry-run to exercise the arithmetic")

    per_arm: dict[str, dict[str, Any]] = {}
    with Elicitor(
        RESULTS / args.cache,
        model=args.model,
        spot_model=None,
        transport=args.transport,
        rest_ratio=args.rest_ratio,
        dry_run=args.dry_run,
    ) as elicitor:
        for arm in arms:
            counts: Counter[str] = Counter()
            untyped = 0
            answered = 0
            sole: set[str] = set()
            for unit in units:
                shipped_system, prompt = render_summary_prompt(unit.text)
                system = (
                    shipped_system
                    if arm == "constrained"
                    else open_system(shipped_system, PROMISE_KINDS)
                )
                schema = (
                    SUMMARY_SCHEMA if arm == "constrained" else open_schema(SUMMARY_SCHEMA)
                )
                for sample in range(args.samples):
                    answer = summarise_once(
                        elicitor,
                        unit.text,
                        unit_id=unit.unit_id,
                        sample=sample,
                        model=args.model,
                        arm=arm,
                        system=system,
                        prompt=prompt,
                        schema=schema,
                    )
                    if answer is None:
                        continue
                    answered += 1
                    kinds = reported_kinds(answer)
                    named = [kind for kind in kinds if kind]
                    untyped += sum(1 for kind in kinds if kind is None)
                    counts.update(named)
                    # "The only kind this promise got" is read per answer: a promise typed once
                    # and never again is exactly the narrow-but-real category the minor-share
                    # cut would otherwise remove for being narrow.
                    if len(set(named)) == 1:
                        sole.update(named)
            total = sum(counts.values()) + untyped
            per_arm[arm] = {
                "answers": answered,
                "untyped_promises": untyped,
                **read_distribution(
                    counts, candidates=PROMISE_KINDS, sole=sole, total=total
                ),
            }
        spend = elicitor.spend()

    # **The registered reading, and a defect in it that running it is what found.**
    #
    # The rule as pre-registered takes the *intersection* of what survives in both arms, on the
    # reasoning that the constrained arm cannot report outside the candidates while the open arm
    # can wander, so requiring both shrinks a guessed taxonomy rather than growing it.
    #
    # It is wrong, and the first run shows how: the open arm has a **free vocabulary**, so a
    # registered kind can be absent from it because the model chose a synonym — `obligation` and
    # `debt` where the constrained arm says `plot`. Requiring the registered *label* to appear
    # verbatim in a free-vocabulary arm is requiring the model to share our terminology, which is
    # exactly the error `AXIS_MATCHERS`' docstring names: generous about vocabulary, strict about
    # topic. Measured on qwen3:14b, the intersection cuts `plot` at 20 of 51 constrained reports
    # — 39% of the debts this book opened — because the open arm never typed the word.
    #
    # **Recorded in the pre-registration rather than dropped after the fact**, which is §87's
    # precedent: the registered number is reported as the registered number, and the corrected
    # reading is printed beside it as a *proposal* requiring an operator act. Silently swapping
    # the rule once the answer was visible would make every future pre-registration in this
    # directory worth less.
    registered = [
        kind
        for kind in PROMISE_KINDS
        if all(kind in per_arm[arm]["keep"] for arm in arms)
    ]
    corrected = list(per_arm["constrained"]["keep"])
    return {
        "study": "promise_kinds",
        "pre_registration": {
            "candidates": list(PROMISE_KINDS),
            "minor_share": MINOR_SHARE,
            "nominate_share": NOMINATE_SHARE,
            "rule": (
                "zero reports cuts; under minor_share cuts unless it was some promise's only "
                "kind; out-of-set at nominate_share or above is a nomination requiring an "
                "operator act; per model, never pooled; the frozen set is the intersection of "
                "the two arms"
            ),
            "known_defect": (
                "the intersection clause requires a registered label to appear verbatim in a "
                "free-vocabulary arm, which asks the model to share our terminology; kept on "
                "the record and reported as registered, with a corrected reading beside it"
            ),
            "arms": list(arms),
        },
        "source": source,
        "scenes": len(units),
        "samples": args.samples,
        "model": args.model,
        "transport": args.transport,
        "dry_run": bool(args.dry_run),
        "arms": per_arm,
        "readings": {
            "registered": {
                "frozen_set": registered,
                "rule": "the intersection of the two arms",
            },
            "corrected_proposal": {
                "frozen_set": corrected,
                "rule": (
                    "the constrained arm alone prunes; the open arm nominates and never cuts"
                ),
                "why": (
                    "the open arm has a free vocabulary, so a registered kind can be absent "
                    "from it because the model chose a synonym; requiring the label verbatim "
                    "asks the model to share our terminology, which AXIS_MATCHERS' rule "
                    "forbids. Post-hoc, so it is a proposal and not a result: freezing it is "
                    "an operator act."
                ),
            },
        },
        "frozen_set": registered,
        "spend": spend,
    }


def selftest() -> int:
    """Prove the reading rule does what it says, on constructed distributions and no calls.

    The point is the same one `axiom_battery.selftest` makes: a rule that has never executed is
    a rule whose first run is also its first test, and the first run is the expensive one.
    """
    candidates = ("plot", "character", "progression", "mystery", "tone")
    failures: list[str] = []

    never = read_distribution(
        Counter({"plot": 10, "character": 10}), candidates=candidates, sole=set(), total=20
    )
    if [entry["kind"] for entry in never["cut"]] != ["progression", "mystery", "tone"]:
        failures.append("a kind nobody reported was not cut")
    if never["keep"] != ["plot", "character"]:
        failures.append("a well-reported kind was not kept")

    rare = read_distribution(
        Counter({"plot": 99, "tone": 1}), candidates=candidates, sole=set(), total=100
    )
    if "tone" in rare["keep"]:
        failures.append("a kind under the minor share was kept")

    rescued = read_distribution(
        Counter({"plot": 99, "tone": 1}), candidates=candidates, sole={"tone"}, total=100
    )
    if "tone" not in rescued["keep"]:
        failures.append("a rare kind that was some promise's only kind was cut anyway")

    nominated = read_distribution(
        Counter({"plot": 80, "worldbuilding": 20}),
        candidates=candidates,
        sole=set(),
        total=100,
    )
    if [entry["kind"] for entry in nominated["nominations"]] != ["worldbuilding"]:
        failures.append("an unregistered kind above the nominate share was not nominated")
    if "worldbuilding" in nominated["keep"]:
        failures.append("a nomination was admitted rather than reported")

    quiet = read_distribution(
        Counter({"plot": 99, "worldbuilding": 1}),
        candidates=candidates,
        sole=set(),
        total=100,
    )
    if quiet["nominations"]:
        failures.append("an unregistered kind below the nominate share was nominated")
    if [entry["kind"] for entry in quiet["unregistered"]] != ["worldbuilding"]:
        failures.append("an unregistered kind below the share was dropped rather than printed")

    empty = read_distribution(Counter(), candidates=candidates, sole=set(), total=0)
    if empty["keep"] or len(empty["cut"]) != len(candidates):
        failures.append("an empty distribution did not cut everything")

    for line in failures:
        print(f"FAIL {line}", file=sys.stderr)
    print("selftest: " + ("FAILED" if failures else "passed"), file=sys.stderr)
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book-db", default=None)
    parser.add_argument("--scenes", type=int, default=None)
    parser.add_argument("--samples", type=int, default=SAMPLES)
    parser.add_argument("--model", default="qwen3:14b")
    parser.add_argument("--transport", default="ollama", choices=("ollama", "cli", "sdk"))
    parser.add_argument("--rest-ratio", type=float, default=1.0)
    parser.add_argument("--cache", default="promise-kinds-raw.jsonl")
    parser.add_argument("--out", default="promise-kinds.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    report = run(args)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / args.out).write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    for arm, block in report["arms"].items():
        print(
            f"{arm:12s} answers={block['answers']:3d} promises={block['reported_promises']:3d} "
            f"keep={block['keep']} nominations="
            f"{[entry['kind'] for entry in block['nominations']]}",
            file=sys.stderr,
        )
    print(
        f"registered reading: {report['readings']['registered']['frozen_set']}",
        file=sys.stderr,
    )
    print(
        f"corrected proposal: {report['readings']['corrected_proposal']['frozen_set']} "
        "(post-hoc; freezing it is an operator act)",
        file=sys.stderr,
    )
    print(f"wrote {RESULTS / args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
