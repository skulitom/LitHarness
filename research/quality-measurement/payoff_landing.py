"""W4: the ledger says this promise was paid. Did anything land?

**The defect is self-grading.** `promises_paid` is reported by the *same* summary call that
reported `promises_opened`, so the ledger's evidence that a debt was settled is the assertion
of the model that said it existed. Nothing independent has ever looked at the scene the ledger
credits with the payoff.

**The instrument is a separate report-channel question.** Two excerpts — the scene that opened
a promise, and the scene the ledger says paid it — and one ask, blind: *what debt does the
second passage settle?* Named, never rated, and with no preference leg, for §89's reason. The
answer is scored against the ledger's own wording by `summarize.check_open_threads`, which is
the shipped matcher for exactly this comparison and carries its own argued-for rule: a
**majority of the thread's distinctive words**, because one shared word between two sentences
about a book with a consistent register is not evidence of anything.

**Three controls, and the middle one is the whole study.**

    paid          opened scene + the scene the ledger credits    the instrument should name it
    mismatched    opened scene + the scene that paid a DIFFERENT promise    it should not
    unpaid        opened scene of a still-open promise + a later scene      it should not
    placebo       the opened scene against itself                          it should not

The bar is the **mismatched control**, not chance: an instrument that says "yes, settled" to
every pair agrees with the ledger constantly and knows nothing, and only a control sharing
every nuisance property — same book, same register, a real payoff scene — separates "this
scene pays something" from "this scene pays *that*".

**What this run can and cannot reach on the corpus in hand, found before a call was bought.**
The only promise ledger in this repository holds **32 promises, all open, none paid** across a
ten-scene book. So the `paid` and `mismatched` arms have no substrate at all, and what remains
is the **false-positive half**: does the instrument name a matching debt when the ledger says
nothing was paid? That half is cheap, available today, and can kill the instrument outright —
an instrument that finds a payoff on unpaid pairs is dead before the expensive half is bought.
What it cannot do is validate the instrument, so the verdict below is NOT VALIDATED and stays
that way until both a ledger with payments and an owner-read set exist.

**The owner-read set is out-of-loop validation and nothing else** (§A6's standing): it never
steers, never seeds a selection, never appears in a prompt. `--emit-owner-sheet` writes the
blind sheet; `--owner-marks` reads it back.

    uv run python research/quality-measurement/payoff_landing.py --selftest
    uv run python research/quality-measurement/payoff_landing.py --dry-run
    uv run python research/quality-measurement/payoff_landing.py --book-db $TOLL --yes
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from elicit import Elicitor  # noqa: E402
from elicitation_study import FAMILY_ALPHA, fisher_exact_greater  # noqa: E402

RESULTS = HERE / "results"

#: Words of each scene shown. A whole scene on both sides doubles the prompt for a question
#: that is about whether a specific debt is settled, and the settling is at the end of a scene
#: far more often than the opening is — so the opened side is shown from its start and the
#: paying side from its end. Declared here rather than tuned, because a window chosen after
#: seeing which windows scored well is a rubric fitted to its answers.
EXCERPT_WORDS = 450

#: The question, byte-frozen. Report channel: it asks the model to *name* a debt, never to rate
#: how well it was paid and never to choose between passages. "or say none" is load-bearing —
#: without it the ask presupposes that something was paid, which is the demand characteristic
#: that produced 195 keep-readings out of 196.
LANDING_QUESTION = (
    "Two passages from the same book. The second comes later.\n\n"
    "Name the one thing left unresolved by the first passage that the second passage settles, "
    "in one sentence — or say none if the second settles nothing the first left open.\n\n"
    "Describe what is settled, not how well it is written."
)

LANDING_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {"debt": {"type": "string"}},
    "required": ["debt"],
    "additionalProperties": False,
}

MAX_TOKENS = 160

#: The response that declines to find a payoff. Frozen with the question; a control arm is
#: cleared by this or by naming something the ledger's own words do not match.
_NONE = ("none", "nothing", "no debt", "does not settle", "doesn't settle", "settles nothing")

#: **The scorer's own floor.** Below this rate on the constructed positive — where the paying
#: passage literally contains the ledger's sentence — the scorer cannot score, and every other
#: number in the run is withheld rather than printed. `latent_crossfamily.py` withholds win
#: rates for a candidate outside its bias band for the same reason: a number that cannot be read
#: is worse than no number, because somebody quotes it six months later.
#:
#: Set at one half, which is the loosest threshold that still means anything: a scorer missing
#: more than half of the cases it was built to catch is not a strict scorer, it is a broken one.
POSITIVE_FLOOR = 0.5

CALL_GUARD = 600


@dataclass(frozen=True, slots=True)
class LedgerPromise:
    promise_id: str
    subject: str
    description: str
    opened_at_key: str
    paid_at_key: str | None
    status: str


@dataclass(frozen=True, slots=True)
class LandingPair:
    pair_id: str
    arm: str
    #: The promise whose wording the answer is scored against.
    promise: LedgerPromise
    opened: str
    later: str


def read_ledger(database: str | Path) -> list[LedgerPromise]:
    """The promise ledger out of a book database. Read-only, no package import needed."""
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        return [
            LedgerPromise(
                promise_id=row["promise_id"],
                subject=row["subject"],
                description=row["description"],
                opened_at_key=row["opened_at_key"],
                paid_at_key=row["paid_at_key"],
                status=row["status"],
            )
            for row in connection.execute(
                "SELECT promise_id, subject, description, opened_at_key, paid_at_key, status "
                "FROM promises ORDER BY opened_at_key, promise_id"
            )
        ]
    finally:
        connection.close()


def read_scenes(database: str | Path) -> dict[str, str]:
    """`{story order key: prose}` for one book, via the export path.

    Keys are `beats_for`'s, so they line up with the ledger's `opened_at_key` without this
    module minting or parsing one — the padding rule `domain/promises.py` insists on.

    **`width` is `beats_for`'s exactly, and the floor of 2 it used to carry emptied every arm
    on any book shorter than ten scenes.** `beats_for` pads to `len(str(len(scenes)))` with no
    minimum, so an eight-scene book's ledger holds `s1…s8` while this minted `s01…s08`; every
    membership test against `scenes` then failed and the census reported four arms of zero as
    if the ledger had supplied nothing. It read as a substrate problem and was a key-width
    problem. Found on `serial.db` (40 promises, 8 scenes, every arm 0) while reporting what
    the ledger could build; `toll.db` is ten scenes, where both rules agree on 2, which is
    why nothing noticed.
    """
    from corpus_io import generated_scenes

    units = generated_scenes(database, min_words=1)
    width = len(str(len(units)))
    return {f"s{index:0{width}d}": unit.text for index, unit in enumerate(units, start=1)}


def head(text: str, *, words: int = EXCERPT_WORDS) -> str:
    return " ".join(text.split()[:words])


def tail(text: str, *, words: int = EXCERPT_WORDS) -> str:
    return " ".join(text.split()[-words:])


def _constructed_payoff(promise: LedgerPromise) -> str:
    """A short passage that settles this promise in the ledger's own words. DIAGNOSTIC only.

    Deliberately built from `description`, which is what makes it a floor test of the matcher
    rather than a test of the reader: any model that reads the passage will echo those words and
    `matches_ledger` will fire. If it does not fire here it cannot fire anywhere, and the
    unpaid arm's zero is a dead matcher rather than a clean instrument.
    """
    return (
        "The matter was settled that afternoon, in front of the whole depot. "
        f"{promise.description[0].upper()}{promise.description[1:]} "
        "It was done, and nobody had cause to raise it again."
    )


def build_pairs(
    promises: list[LedgerPromise], scenes: dict[str, str]
) -> tuple[list[LandingPair], dict[str, Any]]:
    """Every arm's pairs, and a census of what the ledger could and could not supply.

    The census is the honest half: an arm with no substrate is reported with its count at zero
    rather than omitted, because a study reporting three arms of four reads as a study that ran.
    """
    keys = sorted(scenes)
    paid = [p for p in promises if p.status == "paid" and p.paid_at_key in scenes]
    unpaid = [p for p in promises if p.status != "paid" and p.opened_at_key in scenes]
    pairs: list[LandingPair] = []

    for promise in paid:
        pairs.append(
            LandingPair(
                f"paid-{promise.promise_id[:12]}", "paid", promise,
                head(scenes[promise.opened_at_key]),
                tail(scenes[promise.paid_at_key or ""]),
            )
        )
    # Mismatched: this promise's opening against *another* promise's payoff scene. Rotated by
    # one so every paid promise contributes exactly one mismatched pair and no promise is
    # matched with itself — a random draw would make the control's difficulty a property of a
    # seed rather than of the ledger.
    for index, promise in enumerate(paid):
        other = paid[(index + 1) % len(paid)] if len(paid) > 1 else None
        if other is None or other.promise_id == promise.promise_id:
            continue
        pairs.append(
            LandingPair(
                f"mismatch-{promise.promise_id[:12]}", "mismatched", promise,
                head(scenes[promise.opened_at_key]),
                tail(scenes[other.paid_at_key or ""]),
            )
        )
    # Unpaid: an open promise's opening against a *later* scene the ledger credits with nothing.
    # The false-positive arm, and the only one this repository's ledger can currently supply.
    for promise in unpaid:
        later = [key for key in keys if key > promise.opened_at_key]
        if not later:
            continue
        pairs.append(
            LandingPair(
                f"unpaid-{promise.promise_id[:12]}", "unpaid", promise,
                head(scenes[promise.opened_at_key]),
                tail(scenes[later[len(later) // 2]]),
            )
        )
    for promise in unpaid[: max(len(unpaid) // 4, 1)]:
        opening = head(scenes[promise.opened_at_key])
        pairs.append(
            LandingPair(
                f"placebo-{promise.promise_id[:12]}", "placebo", promise, opening, opening
            )
        )
    # **A constructed positive, added after the first run and labelled DIAGNOSTIC.** In no bar,
    # and it is not evidence about the instrument: the second passage is built out of the
    # ledger's own sentence, so a model that reads at all will echo it and the matcher will
    # fire. What it bounds is the *other* reading of a zero false-positive rate. `0 of 32
    # matched` means either the instrument correctly found no matching debt or the matcher
    # cannot fire at all, and `check_open_threads`' own docstring is a record of how easily a
    # majority-of-distinctive-words rule misses — so without this arm the headline number is
    # uninterpretable in exactly the direction that flatters it.
    for promise in unpaid:
        pairs.append(
            LandingPair(
                f"positive-{promise.promise_id[:12]}", "constructed_positive", promise,
                head(scenes[promise.opened_at_key]),
                _constructed_payoff(promise),
            )
        )

    census = {
        "promises": len(promises),
        "paid": len(paid),
        "open": len(promises) - len([p for p in promises if p.status == "paid"]),
        "scenes": len(scenes),
        "arms": {
            arm: sum(1 for pair in pairs if pair.arm == arm)
            for arm in ("paid", "mismatched", "unpaid", "placebo", "constructed_positive")
        },
        "unrunnable": [
            arm
            for arm in ("paid", "mismatched")
            if not any(pair.arm == arm for pair in pairs)
        ],
    }
    return pairs, census


def says_none(said: str) -> bool:
    """Did the answer decline to name a debt? Frozen with the question."""
    lowered = said.strip().lower()
    return not lowered or any(lowered.startswith(marker) for marker in _NONE) or any(
        marker in lowered for marker in ("settles nothing", "no debt", "does not settle")
    )


def _depunctuate(text: str) -> str:
    """Lowercase, punctuation to spaces. The one adaptation, and it is not cosmetic.

    `check_open_threads` splits its thread on whitespace and asks whether each distinctive
    token is a **substring** of the prose, so a recorded token carrying a comma —
    ``"contents,"`` — cannot match a sentence that says *contents*. In its shipped position
    that is harmless: the threads it receives come from `state.describe`, which renders records
    rather than sentences. Here the recorded side is a model-written sentence with ordinary
    punctuation, so without this the match rate would be a property of where the summariser put
    its commas. Applied to **both** sides, so a punctuation-free input is unaffected — asserted
    in `selftest`.
    """
    return "".join(character if character.isalnum() else " " for character in text.lower())


def matches_ledger(said: str, promise: LedgerPromise) -> bool:
    """Does the named debt match the ledger's own wording for this promise?

    **The shipped matcher, imported rather than re-implemented.**
    `summarize.check_open_threads` already answers "does this prose mention this recorded
    thread", and it already carries the argument for its rule — a majority of the thread's
    distinctive words, because the first version matched *"the sealed letter must be read aloud
    at the will reading"* against a summary whose only overlap was the word *aloud*. A second
    matcher here would be a second definition of the same comparison, and the two would drift.
    """
    from litharness.application.summarize import check_open_threads

    if says_none(said):
        return False
    mentioned, _ = check_open_threads(
        _depunctuate(said), [_depunctuate(promise.description)]
    )
    return mentioned > 0


def ask(elicitor: Elicitor, pair: LandingPair, *, model: str) -> dict[str, Any]:
    record = elicitor.ask_raw(
        "You are shown two passages and asked one question about them. Answer only the "
        "question, in one sentence, as a single JSON object.",
        [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"PASSAGE ONE:\n{pair.opened}\n\nPASSAGE TWO:\n{pair.later}"
                        f"\n\n{LANDING_QUESTION}",
                    }
                ],
            }
        ],
        schema=LANDING_SCHEMA,
        max_tokens=MAX_TOKENS,
        tag={"pair": pair.pair_id, "arm": pair.arm, "stage": "landing"},
        model=model,
    )
    said = ""
    if not record.get("refused") and record.get("text"):
        try:
            said = str(json.loads(record["text"]).get("debt", ""))
        except (json.JSONDecodeError, AttributeError):
            said = ""
    return {
        "pair": pair.pair_id,
        "arm": pair.arm,
        "promise": pair.promise.subject,
        "ledger_says": pair.promise.description,
        "said": said,
        "refused": not said,
        "named_none": says_none(said),
        "matches_ledger": matches_ledger(said, pair.promise),
    }


def score(rows: list[dict[str, Any]], census: dict[str, Any]) -> dict[str, Any]:
    """Arm rates, the paid-versus-mismatched bar, and what the substrate refuses to answer."""
    answered = [row for row in rows if not row["refused"]]
    arms: dict[str, dict[str, int]] = {}
    for row in answered:
        cell = arms.setdefault(row["arm"], {"matched": 0, "none": 0, "responses": 0})
        cell["responses"] += 1
        cell["matched"] += int(row["matches_ledger"])
        cell["none"] += int(row["named_none"])

    paid = arms.get("paid", {"matched": 0, "responses": 0})
    mismatched = arms.get("mismatched", {"matched": 0, "responses": 0})
    unpaid = arms.get("unpaid", {"matched": 0, "responses": 0})

    landing = {"verdict": "NOT RUN", "why": "the ledger records no paid promise to pair"}
    if paid["responses"] and mismatched["responses"]:
        p = fisher_exact_greater(
            paid["matched"], paid["responses"] - paid["matched"],
            mismatched["matched"], mismatched["responses"] - mismatched["matched"],
        )
        landing = {
            "verdict": "SEPARATES" if p <= FAMILY_ALPHA else "DOES_NOT",
            "fisher_p": round(p, 6),
            "alpha": FAMILY_ALPHA,
        }

    positive = arms.get("constructed_positive", {"matched": 0, "responses": 0})

    # **The cheap kill, available today.** The unpaid arm needs no payment in the ledger, and a
    # high match rate there ends the instrument before its expensive half is bought: an
    # instrument that finds the debt settled when the ledger says nothing was settled is
    # answering the question's premise rather than the passages.
    false_positive = (
        unpaid["matched"] / unpaid["responses"] if unpaid["responses"] else None
    )
    # **Withheld rather than printed when the scorer cannot score.** A zero false-positive rate
    # has two readings — the instrument correctly found no matching debt, or the matcher cannot
    # fire — and the constructed positive is what separates them. Below `POSITIVE_FLOOR` the
    # second reading is live, so the rate is withheld and the run says why. Printing it with a
    # caveat would not work: the number is what gets quoted.
    positive_rate = (
        positive["matched"] / positive["responses"] if positive["responses"] else None
    )
    scorer_usable = positive_rate is not None and positive_rate >= POSITIVE_FLOOR
    return {
        "arms": arms,
        "landing_bar": landing,
        "false_positive_rate_unpaid": (
            round(false_positive, 4)
            if (false_positive is not None and scorer_usable)
            else None
        ),
        "false_positive_withheld": (
            None
            if scorer_usable
            else (
                "withheld: the scorer fires on "
                f"{positive['matched']}/{positive['responses']} of the constructed positives, "
                f"below the {POSITIVE_FLOOR:.0%} floor, so a zero here is a matcher that "
                "cannot fire rather than an instrument that found nothing"
            )
        ),
        "scorer_usable": scorer_usable,
        "DIAGNOSTIC_constructed_positive_rate": (
            round(positive["matched"] / positive["responses"], 4)
            if positive["responses"] else None
        ),
        "DIAGNOSTIC_reading": (
            "post-hoc and in no bar: the second passage is built from the ledger's own "
            "sentence, so this is a floor test of the matcher and not evidence about the "
            "instrument. A low rate here means the unpaid arm's zero is a dead matcher rather "
            "than a clean instrument, which is the reading that would otherwise flatter it"
        ),
        "census": census,
        # Never VALIDATED here. The pre-registered bar is agreement with an owner-read set on a
        # held-out half, and no such set exists; reporting a machine-only separation as
        # validation would be exactly the promotion §10.4 owns and this study does not.
        "verdict": "NOT VALIDATED" if scorer_usable else "SCORER_UNUSABLE",
        "why": (
            (
                "the pre-registered bar is agreement with an owner-read set, which does not "
                "exist; and the only ledger in this repository records no paid promise, so "
                "the paid and mismatched arms have no substrate"
            )
            if scorer_usable
            else (
                "the pre-registered scorer does not transfer: `check_open_threads` was built "
                "to ask whether a summary of the same prose mentions a recorded thread, and "
                "here it is asked whether a one-sentence paraphrase names the same debt. On "
                "the constructed positive it fires on "
                f"{positive['matched']}/{positive['responses']}, so no other rate in this run "
                "is readable. W4 needs a different scorer before it can be run at all"
            )
        ),
        "wired": False,
    }


def owner_sheet(pairs: list[LandingPair]) -> str:
    """The blind sheet an owner marks, with the ledger's own answer withheld.

    Blind because the ledger's wording is the thing under test: an owner shown "the ledger says
    this settles the sealed crate" is being asked to agree with the ledger, not to read the
    scenes. §8.3's answer-key lesson, one instrument over — strip the key before the grader
    sees the state.
    """
    blocks = ["# Payoff landing — owner sheet", "", "For each pair: does the second passage",
              "settle something the first left open? Write `yes` or `no` after `mark:`,",
              "and if yes, name what in your own words after `what:`.", ""]
    for pair in pairs:
        blocks += [
            f"## {pair.pair_id}",
            "",
            "PASSAGE ONE:",
            pair.opened,
            "",
            "PASSAGE TWO:",
            pair.later,
            "",
            "mark:",
            "what:",
            "",
        ]
    return "\n".join(blocks)


def selftest() -> int:
    """The matcher, the none-detector and the census, before a call is bought."""
    failures: list[str] = []
    promise = LedgerPromise(
        "prm-x", "sealed_crate",
        "The crate's contents, its unfamiliar wax mark, and who sent it must be revealed.",
        "s01", "s05", "paid",
    )
    if not matches_ledger(
        "The second passage reveals the crate's contents and the wax mark and who sent it.",
        promise,
    ):
        failures.append("a clear restatement of the ledger's debt did not match")
    if matches_ledger("The second passage settles an argument about the weather.", promise):
        failures.append("an unrelated debt matched the ledger")
    if matches_ledger("none", promise):
        failures.append("a declined answer matched the ledger")
    if not says_none("None; the second settles nothing the first left open."):
        failures.append("a declining answer was not read as declining")
    if says_none("It settles who sent the crate."):
        failures.append("a naming answer was read as declining")

    # The depunctuation adaptation changes nothing on input that carries no punctuation, which
    # is what makes it an adaptation rather than a second matcher.
    from litharness.application.summarize import check_open_threads

    plain = "the sealed letter must be read aloud at the will reading"
    for said in ("the sealed letter is read aloud at the will reading", "nothing at all"):
        if (check_open_threads(said, [plain])[0] > 0) != (
            check_open_threads(_depunctuate(said), [_depunctuate(plain)])[0] > 0
        ):
            failures.append("depunctuation changed the shipped matcher on plain input")

    scenes = {f"s{index:02d}": f"scene {index} " * 600 for index in range(1, 11)}
    ledger = [
        LedgerPromise(f"prm-{index}", f"subject_{index}", f"a debt about thing {index}",
                      f"s{index:02d}", None, "open")
        for index in range(1, 6)
    ]
    pairs, census = build_pairs(ledger, scenes)
    if census["arms"]["paid"] or census["arms"]["mismatched"]:
        failures.append("an all-open ledger produced paid or mismatched pairs")
    if census["unrunnable"] != ["paid", "mismatched"]:
        failures.append("the census did not name the arms with no substrate")
    if not census["arms"]["unpaid"]:
        failures.append("an all-open ledger produced no unpaid pairs")
    if any(pair.opened == pair.later for pair in pairs if pair.arm != "placebo"):
        failures.append("a non-placebo pair showed the same excerpt twice")
    if not any(pair.opened == pair.later for pair in pairs if pair.arm == "placebo"):
        failures.append("the placebo did not show the same excerpt twice")

    verdict = score([], census)
    if verdict["verdict"] not in {"NOT VALIDATED", "SCORER_UNUSABLE"} or verdict["wired"]:
        failures.append("an unvalidated instrument reported as validated or wired")
    if verdict["landing_bar"]["verdict"] != "NOT RUN":
        failures.append("the landing bar ruled without a paid arm")

    # The withholding rule, which is the one thing in this module that decides whether a number
    # is printed at all. A scorer that cannot clear its own floor must take every rate with it.
    dead = score(
        [{"arm": "unpaid", "refused": False, "matches_ledger": False, "named_none": False,
          "pair": f"u{index}"} for index in range(20)]
        + [{"arm": "constructed_positive", "refused": False, "matches_ledger": index < 2,
            "named_none": False, "pair": f"p{index}"} for index in range(20)],
        census,
    )
    if dead["false_positive_rate_unpaid"] is not None or dead["scorer_usable"]:
        failures.append("a rate was printed under a scorer that cannot clear its own floor")
    if dead["verdict"] != "SCORER_UNUSABLE":
        failures.append("a dead scorer did not read SCORER_UNUSABLE")
    alive = score(
        [{"arm": "unpaid", "refused": False, "matches_ledger": False, "named_none": False,
          "pair": f"u{index}"} for index in range(20)]
        + [{"arm": "constructed_positive", "refused": False, "matches_ledger": index < 18,
            "named_none": False, "pair": f"p{index}"} for index in range(20)],
        census,
    )
    if alive["false_positive_rate_unpaid"] != 0.0 or not alive["scorer_usable"]:
        failures.append("a working scorer's rate was withheld anyway")

    for line in failures:
        print(f"FAIL {line}", file=sys.stderr)
    print("selftest: " + ("FAILED" if failures else "passed"), file=sys.stderr)
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book-db", default=str(HERE / "corpora" / "toll.db"))
    parser.add_argument("--model", default="qwen3:14b")
    parser.add_argument("--transport", default="ollama", choices=("ollama", "cli", "sdk"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--rest-ratio", type=float, default=1.0)
    parser.add_argument("--cache", default="payoff-landing-raw.jsonl")
    parser.add_argument("--out", default="payoff-landing.json")
    parser.add_argument("--emit-owner-sheet", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    promises = read_ledger(args.book_db)
    scenes = read_scenes(args.book_db)
    pairs, census = build_pairs(promises, scenes)
    if args.limit:
        pairs = pairs[: args.limit]
    if args.emit_owner_sheet:
        Path(args.emit_owner_sheet).write_text(owner_sheet(pairs), encoding="utf-8")
        print(f"wrote {args.emit_owner_sheet}", file=sys.stderr)
        return 0

    print(
        f"ledger: {census['promises']} promise(s), {census['paid']} paid; "
        f"{len(pairs)} pair(s) on {args.model} via {args.transport}",
        file=sys.stderr,
    )
    for arm in census["unrunnable"]:
        print(f"  arm {arm}: NO SUBSTRATE (the ledger records no paid promise)", file=sys.stderr)
    if len(pairs) > CALL_GUARD and not args.yes:
        raise SystemExit(f"{len(pairs)} calls is above the {CALL_GUARD} guard; pass --yes")
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
            rows.append(ask(elicitor, pair, model=args.model))
        spend = elicitor.spend()

    report = {
        "study": "payoff_landing",
        "pre_registration": {
            "channel": "report; the question names a debt and never rates or chooses",
            "question": LANDING_QUESTION,
            "excerpt_words": EXCERPT_WORDS,
            "matcher": "summarize.check_open_threads, the shipped thread matcher",
            "bar": (
                "agreement with an owner-read set on its held-out half, clearing the "
                "agreement the mismatched control achieves — never chance"
            ),
            "alpha": FAMILY_ALPHA,
            "owner_set": "out-of-loop validation only; never steers, never in a prompt",
        },
        "book_db": str(args.book_db),
        "model": args.model,
        "transport": args.transport,
        "dry_run": bool(args.dry_run),
        "spend": spend,
        **score(rows, census),
        "responses": rows,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / args.out).write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    for arm, cell in sorted(report["arms"].items()):
        print(
            f"  {arm:12s} matched {cell['matched']:3d}/{cell['responses']:3d}  "
            f"said-none {cell['none']:3d}",
            file=sys.stderr,
        )
    print(
        f"  unpaid false-positive rate: {report['false_positive_rate_unpaid']}",
        file=sys.stderr,
    )
    print(f"  verdict: {report['verdict']}: {report['why']}", file=sys.stderr)
    print(f"wrote {RESULTS / args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
