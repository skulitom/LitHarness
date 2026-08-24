"""Two outlines per world, one told the world and one not, and what separates them.

`plan/handoff-worldbuilding.md` registers P1-P3 and this is the harness that answers them. It
buys one outline call per world per arm and nothing else — no judge, no ranking, no bar. What
comes back is graded by `world_uptake.py`'s counter, which was frozen before this file existed.

**P1 — does a world-aware outline put more of the world into its statements.** The counter, on
the eight statements, world-beyond-premise, on the `coined` leg. The null is the §89.1 class:
instructed variation arriving inert. If there is no separation the lever is not a prompt field,
P4 is not run, and that is the finding.

**P2 — does it leak.** Boundary 3, and the check is `application/summarize.py`'s shipped
`check_open_threads` against every statement written for a scene before a claim's window, plus
every statement at all for an answer this book never reaches. **The shipped matcher is reported
and it is not the whole check, and the reason is arithmetic rather than taste**: it calls a
thread mentioned when *a majority* of its distinctive tokens are present, and this world's six
answers carry 22 to 32 of them, so a 25-word statement would have to be a near-verbatim copy of
a 60-word answer to trip it. A rail whose only leg cannot fire is the shape this repository
already knows as "0 paid is structural", so two more legs run beside it: the same matcher on
depunctuated text (`payoff_landing.py`'s own adaptation, because a recorded answer here is a
model-written sentence and `house,` can never be a substring of `house`), and a
**control-calibrated** overlap check whose floor is the blind arm's own maximum. The blind arm
was never told the answers, so whatever overlap its statements reach is this world's chance
overlap, and a world-aware statement above it is the only kind of hit that means anything.

**P3 — is the reveal planned rather than hoped for.** Do the two window scenes' statements name
their claim. 0 of 2 with P1 positive says the planner took the world and not the schedule.

**Fake first, always.** `--transport fake` wires `FakeProvider` and buys nothing; it exists to
prove the wiring and the readings before a live call is spent, and its statements are canned
text that will separate on nothing. Read `transport` and `failures` in the result file before
reading any number.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
RESULTS = HERE / "results"
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(HERE))

import litharness_contracts as lc  # noqa: E402
import world_uptake as uptake  # noqa: E402

from litharness.application import architect, outline  # noqa: E402
from litharness.application.summarize import check_open_threads  # noqa: E402
from litharness.domain import world_brief, worlds  # noqa: E402
from litharness.domain.beats import arc_template, beats_for  # noqa: E402
from litharness.domain.revision import new_book  # noqa: E402
from litharness.providers import build_default_registry  # noqa: E402

#: The two arms. `blind` is `main` at `83de11c` — the request as it was before a world could
#: reach it. `world_aware` is the same call with the brief.
ARMS: tuple[str, ...] = ("blind", "world_aware")

#: The book shape both arms are rendered against: Serial Pilot 2's own.
SCENES = 8

PRE_REGISTRATION: dict[str, Any] = {
    "written": (
        "2026-08-22, before the first provider call of either arm, against the counter frozen "
        "in world_uptake.py at registration digest cd79c3f56e21a1354e27"
    ),
    "design": (
        "Three forged worlds from one forge run, two arms each, one outline call per cell. "
        "Six live calls. The worlds are pilot2/direct2/forge.json's three candidates; the "
        "picked one is on main as plan/serial-pilot-2-world.json and the other two are NOT "
        "picked -- rendering a request and calling a provider admits nothing to canon, and a "
        "pick is a person's act."
    ),
    "P1": {
        "question": "does a world-aware outline put more of the world into its statements",
        "read": (
            "world_uptake's counter over the eight statements of each arm, "
            "world-beyond-premise, coined leg, share of nameable features named"
        ),
        "null": (
            "no separation -> the planner ignores what it is handed, which is the 89.1 class "
            "of instructed variation arriving inert. Then the lever is not a prompt field, P4 "
            "is not run, and that is what gets reported."
        ),
    },
    "P2": {
        "question": "does it leak",
        "read": (
            "three legs, all reported: (a) check_open_threads(statement, [answer]) as shipped; "
            "(b) the same on depunctuated text; (c) distinctive-token overlap share against a "
            "floor taken from the blind arm's own maximum on the same world."
        ),
        "stop": "any hit on any leg is a stop under boundary 3 and the run is written up",
        "attainability": (
            "leg (a) requires ceil(n/2) of an answer's 22-32 distinctive tokens inside one "
            "statement and can only fire on near-verbatim restatement; that is measured and "
            "reported per claim rather than assumed, and it is why (b) and (c) exist."
        ),
    },
    "P3": {
        "question": "is the reveal planned rather than hoped for",
        "read": "do the two window scenes' statements name their claim",
        "null": "0 of 2 with P1 positive -> the planner took the world and not the schedule",
    },
    "no_bar": (
        "None declared. No model ranks anything here, no judge chooses between arms, nothing "
        "is admitted to any registry and no directive is authored. The only pass/fail outcome "
        "is P2's leak check."
    ),
}


def registration_digest() -> str:
    return uptake.digest(
        {
            "pre_registration": PRE_REGISTRATION,
            "arms": list(ARMS),
            "scenes": SCENES,
            "counter": uptake.registration_digest(),
            "world_rules": list(world_brief.WORLD_RULES),
        }
    )


#: The digest as it stood before the first live call.
FROZEN_DIGEST = "5b58386d638787ef3f1a"


# --- the arms -------------------------------------------------------------------------------


def render(
    candidate: architect.Candidate,
    records: Sequence[lc.StateRecord],
    premise: str,
    *,
    arm: str,
) -> Any:
    """The outline request for one arm. `blind` is the call as `main` made it.

    `premise` is passed in rather than read off the candidate: from 2026-08-24 a forged world
    carries no premise of its own, and `uptake.world_from_forge` is what knows where to find
    it for a bundle from either side of that split.
    """
    revision = new_book("book", "branch", title=candidate.title or "Book", scenes=SCENES)
    beats = beats_for(revision, arc_template(SCENES))

    class _Base:
        plan_revision_id = "planrev-arms"
        items: tuple = ()

    brief = world_brief.brief_for(records) if arm == "world_aware" else None
    return outline.render_outline_request(premise, beats, base=_Base(), world=brief)


def statements_of(payload: Mapping[str, Any]) -> dict[int, str]:
    """The model's scenes as `{ordinal: statement}`. Missing ordinals are reported, not filled."""
    found: dict[int, str] = {}
    for entry in payload.get("scenes") or []:
        if not isinstance(entry, Mapping):
            continue
        ordinal = entry.get("ordinal")
        statement = entry.get("statement")
        if isinstance(ordinal, int) and isinstance(statement, str) and statement.strip():
            found[ordinal] = statement.strip()
    return found


def buy(registry: Any, request: Any) -> dict[str, Any]:
    """One provider call, with everything a later reader needs to distrust it."""
    started = time.monotonic()
    try:
        result, _ = registry.complete(request)
    except Exception as problem:
        return {
            "ok": False,
            "failure": f"{type(problem).__name__}: {problem}",
            "seconds": round(time.monotonic() - started, 2),
        }
    usage = getattr(result, "usage", None)
    return {
        "ok": True,
        "seconds": round(time.monotonic() - started, 2),
        "provider": getattr(result, "provider", None),
        "model": getattr(result, "model", None),
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "parsed": getattr(result, "parsed", None),
        "text": getattr(result, "text", "") or "",
    }


# --- P2, the leak rail ----------------------------------------------------------------------


def depunctuate(text: str) -> str:
    """`payoff_landing.py:298`, restated. Both sides, or the answer is about comma placement."""
    return "".join(char if char.isalnum() else " " for char in text.lower())


def distinctive(text: str) -> list[str]:
    """`check_open_threads`' own tokenisation, on depunctuated text so a token is a word."""
    return [word for word in depunctuate(text).split() if len(word) > 4]


def overlap_share(statement: str, answer: str) -> float:
    """The share of an answer's distinctive tokens present in a statement. [0, 1]."""
    tokens = distinctive(answer)
    if not tokens:
        return 0.0
    page = depunctuate(statement)
    return sum(1 for token in tokens if token in page) / len(tokens)


def leak_check(
    records: Sequence[lc.StateRecord],
    statements: Mapping[int, str],
    *,
    floors: Mapping[str, float],
) -> dict[str, Any]:
    """Boundary 3, three legs, every one of them reported.

    A statement is *before the window* when its ordinal is lower than the reveal's; for an
    answer this book never reaches, every statement is before the window and stays so forever.
    """
    answers = worlds.claims(records)
    questions = worlds.questions(records)
    scheduled = worlds.disclosures(records)
    ordinals = worlds.reveal_scenes(records)
    rows: list[dict[str, Any]] = []
    for claim_id in sorted(questions):
        answer = answers.get(claim_id)
        if not answer:
            continue
        in_book = claim_id in scheduled
        window = ordinals.get(claim_id) if in_book else None
        tokens = distinctive(answer)
        hits: list[dict[str, Any]] = []
        worst = 0.0
        for ordinal in sorted(statements):
            if window is not None and ordinal >= window:
                continue  # at and after its window the answer is an ordinary fact
            statement = statements[ordinal]
            shipped = check_open_threads(statement, [answer])[0] > 0
            folded = check_open_threads(depunctuate(statement), [depunctuate(answer)])[0] > 0
            share = overlap_share(statement, answer)
            worst = max(worst, share)
            floor = floors.get(claim_id)
            over = floor is not None and share > floor
            if shipped or folded or over:
                hits.append(
                    {
                        "scene": ordinal,
                        "shipped_matcher": shipped,
                        "depunctuated_matcher": folded,
                        "overlap_share": round(share, 4),
                        "control_floor": floor,
                        "above_control_floor": over,
                    }
                )
        rows.append(
            {
                "claim_id": claim_id,
                "answered_in_this_book": in_book,
                # **The control that separates transmission from vocabulary.** `brief_for`
                # hands an answer to the planner only where the book reaches its window, so a
                # hit on a claim with `False` here is a hit on text the model was never shown.
                # A check that fires on those is measuring the world's vocabulary rather than
                # its secrets, and the share of hits that land on them is the reading.
                "answer_was_handed_to_the_planner": in_book,
                "window_scene": window,
                "distinctive_tokens": len(tokens),
                # The arithmetic that makes the shipped leg's silence readable rather than
                # reassuring: this many of those tokens must be present inside one statement.
                "shipped_matcher_needs_hits": -(-len(tokens) // 2),
                "max_overlap_share_before_window": round(worst, 4),
                "hits": hits,
            }
        )
    hits = sum(len(row["hits"]) for row in rows)
    unshown = sum(
        len(row["hits"]) for row in rows if not row["answer_was_handed_to_the_planner"]
    )
    by_leg = {
        "shipped_matcher": sum(
            1 for row in rows for hit in row["hits"] if hit["shipped_matcher"]
        ),
        "depunctuated_matcher": sum(
            1 for row in rows for hit in row["hits"] if hit["depunctuated_matcher"]
        ),
        "above_control_floor": sum(
            1 for row in rows for hit in row["hits"] if hit["above_control_floor"]
        ),
    }
    return {
        "claims": rows,
        "leaks": hits,
        "hits_by_leg": by_leg,
        "hits_on_answers_never_shown_to_the_planner": unshown,
        "share_of_hits_on_answers_never_shown": (
            None if not hits else round(unshown / hits, 4)
        ),
        "verdict": "STOP" if hits else "no leak on any leg",
    }


def control_floors(records: Sequence[lc.StateRecord], blind: Mapping[int, str]) -> dict[str, float]:
    """Per claim, the highest overlap the **blind** arm reached before that claim's window.

    The blind arm was never told an answer, so this is chance overlap on this world's own
    vocabulary rather than a placed threshold — and it is the only floor available that neither
    a bar nor a judge had to supply.
    """
    answers = worlds.claims(records)
    scheduled = worlds.disclosures(records)
    ordinals = worlds.reveal_scenes(records)
    floors: dict[str, float] = {}
    for claim_id in worlds.questions(records):
        answer = answers.get(claim_id)
        if not answer:
            continue
        window = ordinals.get(claim_id) if claim_id in scheduled else None
        before = [
            overlap_share(text, answer)
            for ordinal, text in blind.items()
            if window is None or ordinal < window
        ]
        floors[claim_id] = round(max(before), 4) if before else 0.0
    return floors


# --- P1 and P3 ------------------------------------------------------------------------------


def score_statements(
    records: Sequence[lc.StateRecord],
    premise: str,
    statements: Mapping[int, str],
    *,
    ordinary: frozenset[str],
) -> dict[str, Any]:
    """P1's reading: `world_uptake`'s counter over statements, both legs, both views."""
    features = uptake.features_of(records, scenes=SCENES)
    scenes = [
        {"ordinal": ordinal, "scene_plan": statements.get(ordinal, ""), "prose": ""}
        for ordinal in range(1, SCENES + 1)
    ]
    out: dict[str, Any] = {}
    for leg in ("wide", "coined"):
        report = uptake.census(
            features,
            scenes,
            premise=premise,
            ordinary=frozenset() if leg == "wide" else ordinary,
            leg=leg,
        )
        summary = report["all_declared_features"]
        out[leg] = {
            "raw": {
                "nameable": summary["raw"]["nameable"],
                "named_in_plan": summary["raw"]["ever_named_in_plan"],
                "share": summary["raw"]["share_named_in_plan"],
            },
            "beyond_premise": {
                "nameable": summary["beyond_premise"]["nameable"],
                "named_in_plan": summary["beyond_premise"]["ever_named_in_plan"],
                "share": summary["beyond_premise"]["share_named_in_plan"],
            },
            "by_kind_beyond_premise": {
                kind: report["by_kind"][kind]["beyond_premise"]["share_named_in_plan"]
                for kind in uptake.FEATURE_KINDS
            },
        }
    return out


def reveal_landing(
    records: Sequence[lc.StateRecord], statements: Mapping[int, str], *, ordinary: frozenset[str]
) -> dict[str, Any]:
    """P3, as registered and — beside it — by the thing a reveal statement actually contains.

    **The registered reading is the claim's own name set, and it is the wrong instrument for
    this question.** A claim id is `m_holts_date`; a statement that lands its reveal says *her
    father's signature selling the Holt date to Kane*. The id's tokens are `holts` and `date`:
    one is a plural the no-stemming rule cannot match against `Holt`, and the other is a word
    the premise already carries and the shelf already owns. So the registered counter reads a
    landed reveal as a miss and reads an unrelated statement containing the word *call* as a
    hit. It is run as registered and reported as registered, and `answer_overlap` is reported
    beside it because a reveal is made of the **answer's** words rather than of the claim's id.

    `answer_overlap` is P2's leg-(c) statistic pointed at the window scene instead of at the
    scenes before it — the same arithmetic, no new instrument — and it is a distribution with
    the blind arm as its own control rather than a bar.
    """
    features = {f.feature_id: f for f in uptake.features_of(records, scenes=SCENES)}
    answers = worlds.claims(records)
    scheduled = worlds.disclosures(records)
    ordinals = worlds.reveal_scenes(records)
    rows: list[dict[str, Any]] = []
    for claim_id in sorted(scheduled):
        window = ordinals.get(claim_id)
        if window is None:
            continue
        feature = features.get(claim_id)
        statement = statements.get(window, "")
        names = feature.names(ordinary, leg="coined") if feature else frozenset()
        wide = feature.names(frozenset(), leg="wide") if feature else frozenset()
        answer = answers.get(claim_id) or ""
        rows.append(
            {
                "claim_id": claim_id,
                "window_scene": window,
                "statement_present": bool(statement),
                "statement": statement,
                "named_coined": sorted(uptake.named(statement, names)),
                "named_wide": sorted(uptake.named(statement, wide)),
                "answer_overlap": round(overlap_share(statement, answer), 4),
            }
        )
    landed = sum(1 for row in rows if row["named_wide"])
    overlaps = [row["answer_overlap"] for row in rows]
    return {
        "windows": rows,
        "landed": landed,
        "of": len(rows),
        "mean_answer_overlap_at_window": (
            round(sum(overlaps) / len(overlaps), 4) if overlaps else None
        ),
    }


# --- selftest and main ----------------------------------------------------------------------


def selftest() -> int:
    failures: list[str] = []

    def check(claim: str, ok: bool) -> None:
        if not ok:
            failures.append(claim)

    check("two arms, named", ARMS == ("blind", "world_aware"))
    check("the counter is the frozen one", uptake.selftest() == 0)
    check("depunctuation is symmetric", depunctuate("house,") == depunctuate("house "))
    check("overlap is a share", 0.0 <= overlap_share("a b c", "alpha bravo") <= 1.0)
    check("an exact copy overlaps fully", overlap_share("alpha bravo", "alpha bravo") == 1.0)
    check("a disjoint statement overlaps not at all", overlap_share("nothing", "alpha") == 0.0)
    check(
        "an answer of short words has no distinctive tokens and cannot be checked",
        distinctive("it is not so at all") == [],
    )
    # **The parse, checked here because the fake provider cannot check it.** `FakeProvider`
    # answers canned prose rather than the schema, so a fake run parses zero statements and
    # every reading comes out vacuously zero — which looks exactly like a null. This is what
    # makes the dry run a rehearsal of the wiring rather than of the answer.
    parsed = statements_of(
        {
            "scenes": [
                {"ordinal": 2, "statement": "  Wren opens a gate.  "},
                {"ordinal": 1, "statement": "Serrell signs an order."},
                {"ordinal": 3, "statement": "   "},
                {"ordinal": "four", "statement": "not an ordinal"},
                "not an object",
            ]
        }
    )
    check(
        "statements parse by ordinal",
        parsed == {1: "Serrell signs an order.", 2: "Wren opens a gate."},
    )
    check("an empty statement is absent rather than empty", 3 not in parsed)
    check("a malformed entry is dropped rather than raising", len(parsed) == 2)
    check("an answerless payload parses to nothing", statements_of({}) == {})

    package = REPO / "plan" / "serial-pilot-2-world.json"
    if not package.is_file():
        failures.append("the committed pilot world is missing")
    else:
        candidate, records, premise = uptake.world_from_package(package)
        blind = render(candidate, records, premise, arm="blind")
        aware = render(candidate, records, premise, arm="world_aware")
        check("the blind arm carries no world", '"world"' not in blind.prompt)
        check("the world-aware arm carries one", '"world"' in aware.prompt)
        check("the two arms differ", blind.prompt != aware.prompt)
        check(
            "the blind arm is byte-identical to a request built with no world at all",
            blind.prompt
            == outline.render_outline_request(
                premise,
                beats_for(
                    new_book("book", "branch", title=candidate.title, scenes=SCENES),
                    arc_template(SCENES),
                ),
                base=blind and _BaseFor(blind.prompt),
            ).prompt,
        )
        # The leak rail must be able to fire, and the arithmetic that says the shipped leg
        # mostly cannot is computed rather than asserted.
        answers = worlds.claims(records)
        planted = {1: answers["m_holts_date"]}
        fired = leak_check(records, planted, floors={})
        check("a statement that copies an answer verbatim is caught", fired["leaks"] > 0)
        clean = leak_check(records, {1: "Wren opens a gate for somebody else's call."}, floors={})
        check("an ordinary statement is not", clean["leaks"] == 0)

    computed = registration_digest()
    check(
        f"the frozen block still digests to {FROZEN_DIGEST} (computed {computed})",
        computed == FROZEN_DIGEST,
    )
    for message in failures:
        print(f"  FAIL {message}", file=sys.stderr)
    print(
        f"selftest: {'PASS' if not failures else str(len(failures)) + ' FAILURES'} "
        f"(registration digest {computed})",
        file=sys.stderr,
    )
    return 1 if failures else 0


class _BaseFor:
    """Reads the plan revision id back out of a rendered prompt; see `test_world_brief.py`."""

    items: tuple = ()

    def __init__(self, prompt: str) -> None:
        self.plan_revision_id = str(json.loads(prompt)["base_plan_revision_id"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument(
        "--reanalyse",
        default=None,
        help="recompute every reading from a stored result file, buying nothing",
    )
    parser.add_argument("--transport", choices=("fake", "live"), default="fake")
    parser.add_argument("--forge", default=str(REPO / "pilot2" / "direct2" / "forge.json"))
    parser.add_argument("--worlds", default="0,1,2")
    parser.add_argument("--lexicon", default=str(uptake.LEXICON_JSON))
    parser.add_argument("--floor", type=int, default=uptake.ORDINARY_FLOOR)
    parser.add_argument("--out", default=str(RESULTS / "world-plan-arms.json"))
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.reanalyse:
        # **Free, and it exists because a reading should never need a second purchase.** The
        # statements are the evidence; every number in this module is a deterministic function
        # of them, so a corrected or extended reading re-runs over the stored answer rather
        # than over a fresh one that would also differ by sampling.
        if selftest():
            print("refusing to reanalyse: the selftest failed", file=sys.stderr)
            return 1
        stored = json.loads(Path(args.reanalyse).read_text(encoding="utf-8"))
        ordinary = uptake.ordinary_tokens(
            uptake.load_lexicon(Path(args.lexicon)), floor=args.floor
        )
        for cell in stored["cells"]:
            _, records, premise = uptake.world_from_forge(
                Path(args.forge), cell["world_index"]
            )
            said = {
                arm: {int(key): text for key, text in cell["statements"][arm].items()}
                for arm in ARMS
            }
            floors = control_floors(records, said["blind"])
            cell["P2_control_floors"] = floors
            cell["P1"] = {
                arm: score_statements(records, premise, said[arm], ordinary=ordinary)
                for arm in ARMS
            }
            cell["P2"] = {
                arm: leak_check(records, said[arm], floors=floors if arm != "blind" else {})
                for arm in ARMS
            }
            cell["P3"] = {
                arm: reveal_landing(records, said[arm], ordinary=ordinary) for arm in ARMS
            }
        stored["registration_digest"] = registration_digest()
        stored["counter_digest"] = uptake.registration_digest()
        stored["reanalysed"] = True
        out = Path(args.out)
        out.write_text(json.dumps(stored, indent=2, sort_keys=True), encoding="utf-8")
        for cell in stored["cells"]:
            for arm in ARMS:
                p1 = cell["P1"][arm]["coined"]["beyond_premise"]
                p2 = cell["P2"][arm]
                unshown = p2["hits_on_answers_never_shown_to_the_planner"]
                print(
                    f"{cell['title'][:18]:18s} {arm:11s} P1 {p1['named_in_plan']:2d}/"
                    f"{p1['nameable']:2d} = {p1['share']} | P2 {p2['verdict']} "
                    f"legs={p2['hits_by_leg']} unshown={unshown}"
                    f" | P3 {cell['P3'][arm]['landed']}/{cell['P3'][arm]['of']}"
                )
        print(f"reanalysed {args.reanalyse} -> {out}")
        return 0

    if not args.run:
        parser.error("one of --selftest, --run or --reanalyse is required")
    if selftest():
        print("refusing to run: the selftest failed", file=sys.stderr)
        return 1

    if args.transport == "fake":
        os.environ.setdefault("LITHARNESS_FAKE_PAD_CHARS", "400")
    else:
        os.environ.pop("LITHARNESS_FAKE_PAD_CHARS", None)
        os.environ.pop("LITHARNESS_ENV", None)
    registry = build_default_registry()
    ordinary = uptake.ordinary_tokens(
        uptake.load_lexicon(Path(args.lexicon)), floor=args.floor
    )

    cells: list[dict[str, Any]] = []
    failures = 0
    for index in (int(part) for part in args.worlds.split(",") if part.strip()):
        candidate, records, premise = uptake.world_from_forge(Path(args.forge), index)
        answers: dict[str, Mapping[int, str]] = {}
        bought: dict[str, dict[str, Any]] = {}
        for arm in ARMS:
            request = render(candidate, records, premise, arm=arm)
            print(f"  {candidate.title} / {arm}: {len(request.prompt)} chars", file=sys.stderr)
            call = buy(registry, request)
            bought[arm] = {key: call[key] for key in call if key not in {"parsed", "text"}}
            bought[arm]["prompt_chars"] = len(request.prompt)
            if not call["ok"]:
                failures += 1
                answers[arm] = {}
                bought[arm]["statements_parsed"] = 0
                continue
            parsed = call["parsed"]
            if not isinstance(parsed, Mapping):
                try:
                    parsed = json.loads(call["text"])
                except (TypeError, ValueError):
                    parsed = {}
            answers[arm] = statements_of(parsed if isinstance(parsed, Mapping) else {})
            # **Recorded, because zero parsed statements and a genuine null are the same
            # number.** The fake answers canned prose and parses to nothing; a live arm that
            # did the same would report P1 = 0.0 and look like a finding.
            bought[arm]["statements_parsed"] = len(answers[arm])
            if len(answers[arm]) != SCENES:
                print(
                    f"    WARNING {candidate.title} / {arm}: {len(answers[arm])} of {SCENES} "
                    "statements parsed; every reading below is against that and not against "
                    "eight",
                    file=sys.stderr,
                )
        floors = control_floors(records, answers.get("blind", {}))
        cells.append(
            {
                "world_index": index,
                "title": candidate.title,
                "records": len(records),
                "calls": bought,
                "statements": {arm: dict(sorted(answers[arm].items())) for arm in ARMS},
                "P1": {
                    arm: score_statements(records, premise, answers[arm], ordinary=ordinary)
                    for arm in ARMS
                },
                "P2": {
                    arm: leak_check(records, answers[arm], floors=floors if arm != "blind" else {})
                    for arm in ARMS
                },
                "P2_control_floors": floors,
                "P3": {
                    arm: reveal_landing(records, answers[arm], ordinary=ordinary) for arm in ARMS
                },
            }
        )

    report = {
        "protocol": "plan/handoff-worldbuilding.md P1-P3",
        "registration_digest": registration_digest(),
        "counter_digest": uptake.registration_digest(),
        "pre_registration": PRE_REGISTRATION,
        "transport": args.transport,
        "failures": failures,
        "ordinary_floor": args.floor,
        "cells": cells,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    for cell in cells:
        for arm in ARMS:
            p1 = cell["P1"][arm]["coined"]["beyond_premise"]
            print(
                f"{cell['title'][:18]:18s} {arm:11s} P1 {p1['named_in_plan']:2d}/"
                f"{p1['nameable']:2d} = {p1['share']} | P2 {cell['P2'][arm]['verdict']} "
                f"| P3 {cell['P3'][arm]['landed']}/{cell['P3'][arm]['of']}"
            )
    print(f"transport={args.transport} failures={failures}; wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
