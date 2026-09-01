"""The exploratory panel column: the frozen ten-persona panel pointed at two of OUR chapters.

`plan/continuous-loop-direction.md` build 3 is the contract. The backtest's session machinery
was built to post-dict a real market's retained member from two blinded RoyalRoad openings;
this module points exactly that machinery — same personas, same two byte-frozen turns, same
closed schema, same blinding, same replay cache — at two chapter files this project wrote,
typically draw N against draw N-1 of one settled listing. What comes back is a preference
share among ten simulated readers, and it is **pilot-grade evidence with no validity licence**:
every output this module produces carries `PROVENANCE` beside it, and the direction note's
sentence stands unedited — never a gate, never alone a reason to ship or kill, and never
reaching a prompt.

**What this module is not.** It is not an arm of the registered backtest. Its sessions carry
the arm tag `ARM` and pair ids under `PAIR_PREFIX`, so no cached record of ours can be read
back as a registered cell, and it writes its own file to its own cache. It computes no verdict
under PREREG's rule or the amended one, and it cannot: our chapters have no market outcome, so
there is no higher-conversion member, no member space, and nothing for `analysis` to aggregate.
`analysis.Vote` is deliberately not the record type here — its `high_was` field names a market
fact our books do not have, and a field that lies by name is how a number gets promoted. The
reward/holdout split is not reported for the same reason: it exists to decide which personas
may become a reward model under a registration this column does not run.

**The two ceilings.** `elicit.Elicitor` expresses no spend ceiling of its own — it exposes
`spend()` and nothing else — so this module carries the refusal: **both** `--max-usd` and
`--max-sessions` must be expressed (flag or env), neither has a default, the estimate is
checked against both before the first call, and the ledger is read after every session exactly
as `backtest.run_sessions` does. The backtest's own `COST_CEILING_USD` is deliberately not
reused: it is the registered programme's budget, and an exploratory read must not spend against
it.

Research side by construction. Nothing under `src/litharness/` may import this; it opens no
database, writes only one `.json`, and reads no corpus — the only text it touches is ours.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
_QUALITY = HERE.parent / "quality-measurement"
if str(_QUALITY) not in sys.path:
    sys.path.insert(0, str(_QUALITY))
REPO_ROOT = HERE.parent.parent

import arms  # noqa: E402  # sibling research module, imported by path
import backtest  # noqa: E402
import blinding  # noqa: E402
import population  # noqa: E402

#: The fixed sentence that rides beside every number this module produces. It names what the
#: panel's evidence actually is, in the pilot's own terms: a descriptive post-diction at pilot
#: n, control corners that never settled, and no validity licence for the instrument. The text
#: is frozen — a softened provenance is how pilot-grade evidence becomes a gate — and
#: `research/sim-readership-backtest/FINDINGS.md` owns every number it cites.
PROVENANCE: str = (
    "EXPLORATORY: this column reuses the sim-readership backtest's frozen ten-persona panel, "
    "whose only evidence is descriptive — 0.789 post-diction on 19 decided RoyalRoad pairs at "
    "pilot n, control corners unsettled (the sham corner voided and stage (c) is paused), and "
    "no validity licence for the instrument. These shares describe what ten simulated readers "
    "did with two of our own drafts; they gate nothing, rank nothing, promote nothing, and "
    "never reach a prompt."
)

#: The label stamped on the file and on every block inside it, so a number lifted out of the
#: file on its own still carries what it is.
LABEL: str = "exploratory"

#: The arm tag every session here carries. Distinct from every registered arm name
#: (`backtest.CONTROL_ARMS`, "C", "P") so a cached record is attributable on its face.
ARM: str = "house"

#: Pair-id prefix. `arms._sample_index` folds (pair_id, persona_id, order) and **not** the arm,
#: so the prefix is what keeps a house cell's cache key clear of a registered cell's: no
#: registered pair id starts with it (they are 16-hex ids, `sham-*` and `damage-*`).
PAIR_PREFIX: str = "house-"

#: The per-session cost basis, measured by the 2026-08-30 pilot; `backtest.EST_USD_PER_SESSION`
#: carries the same measurement rounded to 0.075 for the ceiling arithmetic, and PREREG.md with
#: FINDINGS.md own the measurement itself. Priced unrounded here because this module's entire
#: cost claim is this one multiplication and a person checks it by hand.
USD_PER_SESSION: float = 0.0747

#: Environment fallbacks for the two required ceilings. Flags win; absence of both forms is a
#: refusal, not a default.
ENV_MAX_USD = "LITHARNESS_PANEL_MAX_USD"
ENV_MAX_SESSIONS = "LITHARNESS_PANEL_MAX_SESSIONS"

#: Substrings no key in the output may contain, case-insensitively. Substring rather than exact
#: match on purpose: `verdict_registered` is precisely the name the dual-verdict lesson is
#: about, and `quality_score` would slip past an exact-name rule. This module reports shares
#: and counts; anything that reads as an adjudication has no home in the file.
FORBIDDEN_KEY_PARTS: tuple[str, ...] = ("verdict", "score")

#: The output is a JSON file a person opens. A store suffix here would mean this module had
#: written into a book's database, which it must never do.
STORE_SUFFIXES: tuple[str, ...] = (".db", ".sqlite", ".sqlite3")

_DEFAULT_MODEL = "claude-haiku-4-5"


class ForbiddenOutput(ValueError):
    """The payload or the destination is one this module refuses to write."""


class CeilingNotExpressed(ValueError):
    """A paid run was asked for without both spend ceilings expressed."""


class Elicits(Protocol):
    """The slice of `elicit.Elicitor` this module uses; a fake satisfies it in tests."""

    def ask_raw(
        self, system: str, turns: list[dict[str, Any]], *, schema: dict[str, object] | None,
        max_tokens: int, tag: dict[str, Any], sample: int = 0, model: str | None = None,
    ) -> dict[str, Any]: ...

    def spend(self) -> dict[str, int | float]: ...


# ------------------------------------------------------------------------------- the stimuli


@dataclass(frozen=True, slots=True)
class Side:
    """One of the two chapter files, after blinding, as it will be shown."""

    label: str
    path: str
    text: str
    digest: str
    words: int
    removed: dict[str, int]

    def as_record(self) -> dict[str, Any]:
        """What the output file says about this side. The text itself never lands there.

        `label` is recorded and never shown: it is how a person tells draw 3 from draw 2 in the
        result, and a label reaching a persona ("draw 3", "the revised one") would be exactly
        the identity leak `blinding` exists to prevent.
        """
        return {
            "label": self.label,
            "path": self.path,
            "digest": self.digest,
            "words": self.words,
            "blinding_removed": dict(self.removed),
        }


def read_side(path: Path, *, label: str, title: str, author: str) -> Side:
    """One chapter file, blinded and capped, ready to be shown to a persona.

    Blinding is `blinding.blind` unchanged: it strips the given title and author in their
    normalised forms plus chapter-heading lines, URLs, platform lines and author's-note blocks,
    and touches nothing else. Our exported chapters routinely open with a `# Chapter 7` line and
    may carry a title the listing named, so this is not ceremony — an unblinded pair would let a
    persona answer on which file looked like a draft rather than on the prose.

    The C-arm's paragraph cap is applied afterwards for stimulus-shape parity with the machinery
    being reused; at our chapter lengths it does not bite, and when it does it cuts between
    paragraphs. An empty or whitespace-only file raises here rather than becoming half a
    comparison downstream.
    """
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        raise ForbiddenOutput(f"{path} is empty; an empty stimulus is not a stimulus")
    blinded = blinding.blind(raw, title=title, author=author)
    capped = arms._cap_paragraph(blinded.text)
    return Side(
        label=label,
        path=str(path),
        text=capped,
        digest=hashlib.sha256(capped.encode("utf-8")).hexdigest(),
        words=len(capped.split()),
        removed=dict(blinded.removed),
    )


def pair_id_for(side_a: Side, side_b: Side) -> str:
    """A stable house pair id from both blinded digests, in file order.

    Swapping the two files is a different experiment and gets a different id, hence different
    sample indices and no accidental replay of the other direction's draws.
    """
    material = f"{side_a.digest}\x00{side_b.digest}".encode()
    return f"{PAIR_PREFIX}{hashlib.sha256(material).hexdigest()[:16]}"


def plan_sessions(
    side_a: Side, side_b: Side, personas: Sequence[population.Persona] = population.POPULATION,
) -> list[backtest.PlannedSession]:
    """Ten personas x both orders for the one house pair, via the backtest's own cell builder.

    `backtest._sessions_for_pair` is reused rather than reimplemented so the cell shape, the
    both-orders rotation and the degenerate-stimuli refusal are literally the ones the registered
    arms run under. Its parameters are named `high_text`/`low_text` after the market fact the
    backtest has and we do not: here the first slot is simply file A, positionally, and
    `arms.ordered` still applies the order in the one place it is ever applied.

    Byte-identical or empty stimuli raise `backtest.DegenerateStimuli` by name — the case that
    matters most for us, since draw N and draw N-1 of one listing can genuinely come back
    identical, and twenty sessions asking a persona to choose between a text and itself would
    return a coin this file would print as a preference.
    """
    return backtest._sessions_for_pair(
        pair_id_for(side_a, side_b), ARM, side_a.text, side_b.text, personas
    )


# ------------------------------------------------------------------------------- the paid loop


@dataclass(frozen=True, slots=True)
class PanelAnswer:
    """One persona's parsed stage-2 answer, in slot space, plus which file held slot A."""

    persona_id: str
    order: int
    choice: str  # "A" | "B" | "neither" — the slot, as shown
    reason: str

    @property
    def file_choice(self) -> str:
        """The answer in file space: which of the two files this reader would continue.

        Order 0 shows file A first, order 1 shows file B first (`arms.ordered`), so the mapping
        is the rotation read backwards. "neither" is a reader's decision and survives untouched.
        """
        if self.choice == "neither":
            return "neither"
        first, second = ("file_a", "file_b") if self.order == 0 else ("file_b", "file_a")
        return first if self.choice == "A" else second


def run_panel(
    elicitor: Elicits, planned: Sequence[backtest.PlannedSession], *, model: str,
    ledger: dict[str, float], max_usd: float,
) -> tuple[list[PanelAnswer], bool]:
    """Run the planned sessions; return (answers, aborted_at_ceiling).

    The loop is `backtest.run_sessions`' shape — two turns, stage 1 free text carried into
    stage 2, `arms.parse_stage2`'s one-outcome strictness, the ledger read from `spend()` after
    every session — with this module's own ceiling in place of the registered programme's. A
    crossing finishes the session in hand, stops, and raises the flag to the caller, which
    records it on the face of the file: a partial read that does not say it is partial is the
    failure this whole directory is organised against.

    `spend()` sums the entire cache, replayed records included, so the ledger is cumulative over
    the cache file rather than fresh-spend-only. That is conservative in the right direction: it
    can only ever abort earlier than a fresh-only ledger would.
    """
    answers: list[PanelAnswer] = []
    for session in planned:
        request = arms.build_session(session.spec, session.system, session.text_a, session.text_b)
        stage1 = elicitor.ask_raw(
            request["system"], request["plan"][0]["turns"], schema=None,
            max_tokens=request["plan"][0]["max_tokens"], tag=request["tag"],
            sample=request["sample"], model=model,
        )
        turns = [
            *request["plan"][0]["turns"],
            {"role": "assistant", "content": stage1.get("text") or ""},
            *request["plan"][1]["turns"],
        ]
        stage2 = elicitor.ask_raw(
            request["system"], turns, schema=request["plan"][1]["schema"],
            max_tokens=request["plan"][1]["max_tokens"], tag=request["tag"],
            sample=request["sample"], model=model,
        )
        parsed = arms.parse_stage2(stage2.get("text") or "")
        if parsed is not None:
            choice, reason = parsed
            answers.append(
                PanelAnswer(
                    persona_id=session.spec.persona_id, order=session.spec.order,
                    choice=choice, reason=reason,
                )
            )
        spend = elicitor.spend() if hasattr(elicitor, "spend") else {}
        ledger["equivalent_usd"] = float(spend.get("equivalent_usd", 0.0))
        if ledger["equivalent_usd"] >= max_usd:
            return answers, True
    return answers, False


# --------------------------------------------------------------------------------- the tally


def _share(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0.0


def _shares_over(answers: Sequence[PanelAnswer]) -> dict[str, Any]:
    """Counts and shares for one group of answers. Shares only; nothing is ranked or summed."""
    choices = [answer.file_choice for answer in answers]
    returned = len(choices)
    file_a = choices.count("file_a")
    file_b = choices.count("file_b")
    neither = choices.count("neither")
    decided = file_a + file_b
    return {
        "returned": returned,
        "decided": decided,
        "neither": neither,
        "file_a": file_a,
        "file_b": file_b,
        "share_of_returned": {
            "file_a": _share(file_a, returned),
            "file_b": _share(file_b, returned),
            "neither": _share(neither, returned),
        },
        "share_of_decided": {
            "file_a": _share(file_a, decided),
            "file_b": _share(file_b, decided),
        },
    }


def shares(
    answers: Sequence[PanelAnswer],
    personas: Sequence[population.Persona] = population.POPULATION,
) -> dict[str, Any]:
    """Aggregate and per-persona preference shares. Every persona appears, zeroes included.

    A persona whose sessions all failed to parse is reported at zero rather than dropped: a
    per-persona table that silently loses a reader reads as a panel that never asked it.
    """
    by_persona = {
        persona.persona_id: _shares_over(
            [a for a in answers if a.persona_id == persona.persona_id]
        )
        for persona in personas
    }
    return {
        LABEL: True,
        "aggregate": _shares_over(answers),
        "by_persona": by_persona,
    }


def positional(answers: Sequence[PanelAnswer]) -> dict[str, Any]:
    """The positional split: how often a decided reader took the slot it was shown first.

    Reported in SLOT space, never file space — it is the artifact the both-orders rotation
    exists to expose, and folding it into file space would hide it. A share far from 0.5 here
    says the panel answered on position, which is a reason to distrust the file-space shares in
    the same file.
    """
    decided = [a for a in answers if a.choice in ("A", "B")]
    by_order: dict[str, Any] = {}
    for order in (0, 1):
        subset = [a for a in decided if a.order == order]
        first = sum(1 for a in subset if a.choice == "A")
        by_order[str(order)] = {
            "decided": len(subset),
            "first_slot": first,
            "first_slot_share": _share(first, len(subset)),
        }
    first_slot = sum(1 for a in decided if a.choice == "A")
    return {
        LABEL: True,
        "decided": len(decided),
        "first_slot": first_slot,
        "first_slot_share": _share(first_slot, len(decided)),
        "by_order": by_order,
    }


def reason_counts(answers: Sequence[PanelAnswer]) -> dict[str, Any]:
    """Counts per closed reason code, every code present. Descriptive; nothing reads them."""
    return {
        LABEL: True,
        "counts": {
            code: sum(1 for a in answers if a.reason == code) for code in arms.REASON_CODES
        },
    }


def cost_note(sessions: int) -> str:
    """The one-line cost note printed per run, and the arithmetic a person checks by hand."""
    return (
        f"{LABEL}: cost note — {sessions} session(s) x ${USD_PER_SESSION:.4f}/session "
        f"= ${estimated_usd(sessions):.2f} subscription-equivalent"
    )


def estimated_usd(sessions: int) -> float:
    return round(sessions * USD_PER_SESSION, 4)


# ---------------------------------------------------------------------------- writing the file


def forbidden_keys(payload: object, prefix: str = "") -> list[str]:
    """Every key path in `payload` whose key names an adjudication. Empty is the only pass."""
    found: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if any(part in str(key).casefold() for part in FORBIDDEN_KEY_PARTS):
                found.append(path)
            found.extend(forbidden_keys(value, path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            found.extend(forbidden_keys(value, f"{prefix}[{index}]"))
    return found


def check_destination(path: Path) -> None:
    """Raise unless `path` is a plain `.json` file this module may write.

    A destination that is a database is refused by suffix: this column has no business writing
    into a book store, and the way that rule survives a later edit is a raise rather than a
    sentence. Called twice on purpose — once before any call is bought, so a mistyped
    destination costs nothing, and once inside `write_result`, so no other caller can route
    around it.
    """
    if path.suffix.lower() in STORE_SUFFIXES:
        raise ForbiddenOutput(
            f"{path} is a store; this column writes one .json a person reads and nothing else"
        )
    if path.suffix.lower() != ".json":
        raise ForbiddenOutput(f"{path}: the result is a .json file, got {path.suffix!r}")


def write_result(payload: dict[str, Any], path: Path) -> None:
    """Write the result, or refuse. Both refusals are structural, not documentary.

    The destination is checked by `check_destination`. A payload carrying a key that reads as
    an adjudication is refused by name — the dual-verdict lesson, enforced on the bytes about to
    be written rather than on the schema somebody remembered to keep in step.
    """
    check_destination(path)
    offending = forbidden_keys(payload)
    if offending:
        raise ForbiddenOutput(
            "the result may name no verdict and no score; offending key(s): "
            + ", ".join(sorted(offending))
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )


def build_result(
    side_a: Side, side_b: Side, planned: Sequence[backtest.PlannedSession],
    answers: Sequence[PanelAnswer], *, model: str, ledger: dict[str, float],
    max_usd: float, max_sessions: int, aborted: bool, elicitor: object = None,
) -> dict[str, Any]:
    """The whole result payload. Shares and counts; no verdict, no score, no rank."""
    planned_n = len(planned)
    returned = len(answers)
    return {
        LABEL: True,
        "provenance": PROVENANCE,
        "reads": "one person; nothing downstream consumes this file",
        "panel": {
            "arm": ARM,
            "pair_id": planned[0].spec.pair_id if planned else pair_id_for(side_a, side_b),
            "model": model,
            "population_digest": population.population_digest(),
            "personas": len(population.POPULATION),
            "orders": [0, 1],
        },
        "inputs": {"file_a": side_a.as_record(), "file_b": side_b.as_record()},
        "sessions": {
            "planned": planned_n,
            "returned": returned,
            "unanswered": planned_n - returned,
            "aborted_at_ceiling": aborted,
            "transport_failures": getattr(elicitor, "transport_failures", None),
            "fresh_calls": getattr(elicitor, "api_calls", None),
            "replayed_calls": getattr(elicitor, "replayed", None),
        },
        "shares": shares(answers),
        "positional": positional(answers),
        "reason_codes": reason_counts(answers),
        "cost": {
            "sessions": planned_n,
            "usd_per_session_basis": USD_PER_SESSION,
            "estimated_usd": estimated_usd(planned_n),
            "ledger_usd": round(ledger.get("equivalent_usd", 0.0), 4),
            "ledger_is_cumulative_over_cache": True,
            "max_usd": max_usd,
            "max_sessions": max_sessions,
        },
    }


# ----------------------------------------------------------------------------------- the CLI


def _ceiling(flag: float | int | None, env_name: str, kind: str) -> float:
    """One ceiling from flag or env, or a refusal naming both ways to express it."""
    if flag is not None:
        value = float(flag)
    else:
        raw = os.environ.get(env_name)
        if raw is None or not raw.strip():
            raise CeilingNotExpressed(
                f"no {kind} ceiling expressed: pass --{kind.replace('_', '-')} or set "
                f"{env_name}. Both ceilings are required and neither has a default."
            )
        try:
            value = float(raw)
        except ValueError:
            raise CeilingNotExpressed(f"{env_name}={raw!r} is not a number") from None
    if value <= 0:
        raise CeilingNotExpressed(f"the {kind} ceiling must be positive, got {value}")
    return value


def _default_elicitor(cache: Path, model: str) -> Any:
    """The real elicitor, imported lazily so no refusal path ever needs the API client.

    `spot_model=None` and `transport="cli"` match `backtest.run_paid`: the CLI transport is the
    one carrying §109's CLAUDE.md-suppression flags, and a spot model would be a second tier
    answering some cells of one read.
    """
    import elicit

    return elicit.Elicitor(cache_path=cache, model=model, spot_model=None, transport="cli")


def main(argv: list[str] | None = None, *, elicitor_factory: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--a", required=True, help="chapter file shown as file A (e.g. draw N)")
    parser.add_argument("--b", required=True, help="chapter file shown as file B (e.g. draw N-1)")
    parser.add_argument("--label-a", default=None, help="recorded in the result, never shown")
    parser.add_argument("--label-b", default=None, help="recorded in the result, never shown")
    parser.add_argument("--title", default="", help="listing title to blind out of both files")
    parser.add_argument("--author", default="", help="author/writer name to blind out")
    parser.add_argument("--model", default=_DEFAULT_MODEL)
    parser.add_argument("--cache", default=str(REPO_ROOT / "runs" / "ab" / "panel-cache.jsonl"))
    parser.add_argument("--out", default=None, help="default: runs/ab/panel-<pair_id>.json")
    parser.add_argument("--max-usd", type=float, default=None, help=f"required; or {ENV_MAX_USD}")
    parser.add_argument(
        "--max-sessions", type=int, default=None, help=f"required; or {ENV_MAX_SESSIONS}"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="plan the sessions, print the cost note, construct no elicitor, spend nothing",
    )
    args = parser.parse_args(argv)

    side_a = read_side(
        Path(args.a), label=args.label_a or Path(args.a).stem, title=args.title,
        author=args.author,
    )
    side_b = read_side(
        Path(args.b), label=args.label_b or Path(args.b).stem, title=args.title,
        author=args.author,
    )
    try:
        planned = plan_sessions(side_a, side_b)
    except backtest.DegenerateStimuli as refusal:
        print(f"{LABEL}: refused — {refusal}", file=sys.stderr)
        return 1

    print(f"{LABEL}: {len(planned)} session(s) over {len(population.POPULATION)} persona(s) "
          f"x 2 order(s), arm {ARM!r}, pair {planned[0].spec.pair_id}")
    print(cost_note(len(planned)))
    print(f"{LABEL}: {PROVENANCE}")

    if args.dry_run:
        print(f"{LABEL}: dry run — no elicitor constructed, nothing spent", file=sys.stderr)
        return 0

    try:
        max_usd = _ceiling(args.max_usd, ENV_MAX_USD, "max_usd")
        max_sessions = int(_ceiling(args.max_sessions, ENV_MAX_SESSIONS, "max_sessions"))
    except CeilingNotExpressed as refusal:
        print(f"{LABEL}: refused — {refusal}; nothing was spent", file=sys.stderr)
        return 1
    if len(planned) > max_sessions:
        print(
            f"{LABEL}: refused — {len(planned)} planned session(s) exceed the "
            f"--max-sessions ceiling of {max_sessions}; nothing was spent",
            file=sys.stderr,
        )
        return 1
    estimate = estimated_usd(len(planned))
    if estimate > max_usd:
        print(
            f"{LABEL}: refused — the estimate ${estimate:.2f} exceeds the --max-usd ceiling of "
            f"${max_usd:.2f}; nothing was spent",
            file=sys.stderr,
        )
        return 1

    out_path = Path(args.out) if args.out else (
        REPO_ROOT / "runs" / "ab" / f"panel-{planned[0].spec.pair_id}.json"
    )
    try:
        check_destination(out_path)
    except ForbiddenOutput as refusal:
        print(f"{LABEL}: refused — {refusal}; nothing was spent", file=sys.stderr)
        return 1

    make_elicitor = elicitor_factory or _default_elicitor
    elicitor = make_elicitor(Path(args.cache), args.model)
    ledger: dict[str, float] = {"equivalent_usd": 0.0}
    answers, aborted = run_panel(
        elicitor, planned, model=args.model, ledger=ledger, max_usd=max_usd
    )
    result = build_result(
        side_a, side_b, planned, answers, model=args.model, ledger=ledger,
        max_usd=max_usd, max_sessions=max_sessions, aborted=aborted, elicitor=elicitor,
    )
    try:
        write_result(result, out_path)
    except ForbiddenOutput as refusal:
        print(f"{LABEL}: refused to write — {refusal}", file=sys.stderr)
        return 1

    aggregate = result["shares"]["aggregate"]
    print(
        f"{LABEL}: {aggregate['returned']} returned, {aggregate['decided']} decided, "
        f"{aggregate['neither']} neither"
    )
    print(
        f"{LABEL}: shares of returned — file_a "
        f"{aggregate['share_of_returned']['file_a']}, file_b "
        f"{aggregate['share_of_returned']['file_b']}, neither "
        f"{aggregate['share_of_returned']['neither']}"
    )
    print(f"{LABEL}: first-slot share {result['positional']['first_slot_share']} of "
          f"{result['positional']['decided']} decided")
    if aborted:
        print(f"{LABEL}: STOPPED at the ${max_usd:.2f} ceiling; the file is partial",
              file=sys.stderr)
    print(f"{LABEL}: wrote {out_path} — a person reads it; nothing gates on it")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
