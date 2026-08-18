"""Is the shipped summariser stable enough for anything to be built on top of it?

§71 ships a per-scene summary call whose structured answer feeds the promise ledger
(migration 023), the delta annotation (`craft.scene_delta.v0`), and the context budget. Two
directions the reader work keeps arriving at — *does one summary flow into the next?* and *how
far does a summary-of-summaries drift from what it summarises?* — are both measurements **through**
that call. Neither can be read before the call's own re-sample variance is known, and this module
is the check that produces it.

**The failure mode being guarded against has already killed one instrument in this repo.**
`tree-Haar scale energy` died at ICC(1) = 0.270 with within-book sd equal to between-book sd: its
replicates of one book disagreed as much as different books did, so every hierarchy built on it
was arithmetic over noise. A summariser has exactly that shape — a compression whose output is
re-sampled per scene — and a flow measure over unstable summaries would reproduce the same death
one level up, at the cost of a full sweep to find out.

**Reliability alone is not the test; separation is.** A summariser that answers "two characters,
one promise opened" for every scene in the book is perfectly reliable and carries nothing. So every
statistic here is reported against a between-scene contrast: within-scene agreement means something
only in the amount by which it exceeds agreement between summaries of *different* scenes. That is
the same discipline the persona work runs on shams — a detection rate is read against its placebo,
never alone — and it is the specific check tree-Haar's ICC was doing implicitly and the flow
proposal would not have done at all.

**What is measured is the prompt and the schema, not the production job.** `render_summary_prompt`
is a pure function and `SUMMARY_SCHEMA` is a constant, so both can be called without the store, the
job queue, or a provider profile. What that leaves outside the frame is real and named here rather
than discovered later: the production path runs the `mechanical` profile through a configured
provider, this runs a flag-selected model through `elicit`'s transport, and `--effort` defaults to
unset. A reliability number from here bounds the shipped call from *above* only if the transports
agree; where they do not, this measures the prompt's own stability, which is the part every
downstream proposal inherits regardless of provider.

**Level 2 is a proposal, not a component.** `context.py` evicts summaries under budget, so
summaries-of-summaries do not exist in this system today — their absence is what the eviction costs.
The `--level 2` arm therefore measures something that would have to be built, and it is gated: if
level 1 fails its identity condition, the level-2 numbers are printed as diagnostics and no verdict
is drawn from them, because a drift measurement over summaries that do not identify their own
scenes is measuring the sampler.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from itertools import combinations
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from corpus_io import Unit, fixture_scenes, generated_scenes  # noqa: E402
from elicit import PANEL_MODEL, Elicitor, digest  # noqa: E402
from persona_battery import icc1  # noqa: E402

#: Calls above which the run refuses without `--yes`. One call per (scene, sample), plus the
#: level-2 windows. Lower than the persona battery's guard because this is a diagnostic that
#: should never be the expensive thing in a session.
CALL_GUARD = 600

#: Token headroom per answer. The prompt asks for ~60 words across the prose fields; the rest is
#: the structured envelope and whatever reasoning the transport prepends.
MAX_TOKENS = 2_000

#: Per-summary scalars, each one an input something downstream already consumes.
NUMERIC_FIELDS = (
    "delta_present",
    "n_promises_opened",
    "n_promises_paid",
    "n_characters",
    "prose_words",
)

#: Per-summary sets. `characters` is the identity probe — a summary that cannot name the same
#: people twice is not describing a scene — and the two promise fields are the ledger's inputs.
SET_FIELDS = ("characters", "promises_opened", "promises_paid")

#: Splitters for the `characters` string, which the prompt asks for as prose rather than a list.
_NAME_SPLITS = (";", ",", " and ", " & ")

#: Dropped from a name before comparison. Deliberately short: an aggressive stoplist would
#: manufacture agreement by deleting the words the summaries actually differ on.
_NAME_NOISE = frozenset({"the", "a", "an", "his", "her", "their", "its", "and"})

#: Pre-registered before the first call, in the sense §69 established: the family is one comparison
#: because it was named before the data. Each entry is a condition on the number to its left, and a
#: failure is a stop rather than a note.
PRE_REGISTRATION: dict[str, str] = {
    "identity": (
        "characters within-scene Jaccard minus between-scene Jaccard >= 0.30, or the summary "
        "does not identify its own scene and no flow or drift measure over it is interpretable"
    ),
    "ledger": (
        "ICC(1) on n_promises_opened >= 0.50, or the promise ledger's inputs are re-sample "
        "noise and migration 023 is recording the sampler"
    ),
    "delta": (
        "ICC(1) on delta_present >= 0.50, or §61 Add 1's delta correlation work has no stable "
        "left-hand side"
    ),
    "positivity": (
        "no numeric field is constant across the whole grid; a field that never varies has "
        "undefined variance components and carries no signal, which is how gate 0 died"
    ),
    "level2": (
        "level-2 retention of its own window's promise subjects exceeds retention of a foreign "
        "window's by >= 0.20, or the summary-of-summaries is not carrying what it summarises"
    ),
}


# --------------------------------------------------------------------------- feature extraction


def _name_set(raw: object) -> frozenset[str]:
    """Normalised names out of a prose string or a list of subjects.

    Splitting prose on commas and `and` is a heuristic and is allowed to be one: it is applied
    identically to both sides of every comparison, so a systematic mis-split shifts the within and
    between numbers together and leaves their difference — the quantity every condition is stated
    on — intact. A parser-free control (`characters_tokens`) is reported beside it.
    """
    items: list[str] = []
    if isinstance(raw, str):
        text = raw
        for splitter in _NAME_SPLITS:
            text = text.replace(splitter, "|")
        items = text.split("|")
    elif isinstance(raw, list):
        for entry in raw:
            if isinstance(entry, str):
                items.append(entry)
            elif isinstance(entry, dict):
                items.append(str(entry.get("subject", "")))
    names = set()
    for item in items:
        cleaned = "".join(character if character.isalnum() else " " for character in item.lower())
        words = [word for word in cleaned.split() if word not in _NAME_NOISE]
        if words:
            names.add(" ".join(words))
    return frozenset(names)


def _token_set(raw: object) -> frozenset[str]:
    """Bag of content words. The control for `_name_set`: no splitting rule to get wrong."""
    text = raw if isinstance(raw, str) else json.dumps(raw, sort_keys=True)
    cleaned = "".join(character if character.isalnum() else " " for character in text.lower())
    return frozenset(word for word in cleaned.split() if word not in _NAME_NOISE and len(word) > 2)


def jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    """Intersection over union, with two empty sets scored as full agreement.

    That convention is safe **only** because every use of this is a within-versus-between
    difference. Two summaries that both report no promises paid have agreed, and scoring that as
    zero would penalise a correct answer; the degenerate case it opens — a field that is empty
    everywhere, scoring 1.0 for every pair — is caught by the between-scene contrast, which is also
    1.0, so the separation is zero and the field reads as carrying nothing. Read alone, this number
    would be a trap.
    """
    if not left and not right:
        return 1.0
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def features(summary: dict[str, Any]) -> dict[str, Any]:
    """One summary's scalars and sets. Missing fields are absences, never zeros by default."""
    delta = summary.get("delta")
    opened = summary.get("promises_opened") or []
    paid = summary.get("promises_paid") or []
    characters = _name_set(summary.get("characters", ""))
    prose = " ".join(
        str(summary.get(field, "")) for field in ("setting", "characters", "events", "open")
    )
    return {
        "delta_present": 1.0 if isinstance(delta, dict) and delta.get("what_changed") else 0.0,
        "n_promises_opened": float(len(opened)) if isinstance(opened, list) else 0.0,
        "n_promises_paid": float(len(paid)) if isinstance(paid, list) else 0.0,
        "n_characters": float(len(characters)),
        "prose_words": float(len(prose.split())),
        "characters": characters,
        "characters_tokens": _token_set(summary.get("characters", "")),
        "promises_opened": _name_set(opened),
        "promises_paid": _name_set(paid),
    }


# ------------------------------------------------------------------------------- the statistics


def separation(per_unit: dict[str, list[dict[str, Any]]], field: str) -> dict[str, float]:
    """Within-unit agreement against between-unit agreement, for one set field.

    Both halves are means over *all* available pairs rather than a sample, so the number does not
    move between runs and there is no seed to record. The between half pools across every
    cross-unit pair including pairs of different sample indices, because that is the comparison a
    downstream consumer actually makes: it holds two summaries and asks whether they describe the
    same scene, not whether they were the k-th draw of anything.
    """
    within_pairs: list[float] = []
    for records in per_unit.values():
        for left, right in combinations(records, 2):
            within_pairs.append(jaccard(left[field], right[field]))
    between_pairs: list[float] = []
    unit_ids = sorted(per_unit)
    for left_id, right_id in combinations(unit_ids, 2):
        for left in per_unit[left_id]:
            for right in per_unit[right_id]:
                between_pairs.append(jaccard(left[field], right[field]))
    within = statistics.fmean(within_pairs) if within_pairs else float("nan")
    between = statistics.fmean(between_pairs) if between_pairs else float("nan")
    gap = within - between
    return {
        "within": round(within, 4),
        "between": round(between, 4),
        "separation": round(gap, 4) if not math.isnan(gap) else float("nan"),
        "within_pairs": len(within_pairs),
        "between_pairs": len(between_pairs),
    }


def numeric_report(per_unit: dict[str, list[dict[str, Any]]], field: str) -> dict[str, object]:
    """ICC(1) for one scalar, with the constant case named rather than reported as a number.

    A field the model answers identically everywhere has zero between-unit and zero within-unit
    variance, and `icc1` returns NaN for it. Gate 0 died in exactly that shape — 195 of 196
    `keep-reading`, both mean squares exactly 0.0 — and it took a manual read of the raw records to
    see that the undefined statistic was the finding rather than a bug. Here the degenerate case is
    detected first and labelled, so the run reports it in the same breath as the number.
    """
    groups = [[record[field] for record in records] for records in per_unit.values()]
    flat = [value for group in groups for value in group]
    if not flat:
        return {"status": "empty"}
    if len(set(flat)) == 1:
        return {
            "status": "constant",
            "value": flat[0],
            "n": len(flat),
            "note": "no variance anywhere; ICC undefined and the field carries no signal",
        }
    report: dict[str, object] = dict(icc1(groups))
    report["status"] = "measured"
    report["mean"] = round(statistics.fmean(flat), 4)
    report["sd"] = round(statistics.pstdev(flat), 4) if len(flat) > 1 else 0.0
    return report


def retention(parts: list[dict[str, Any]], whole: dict[str, Any]) -> float:
    """Share of a window's opened-promise subjects that survive into the summary above it.

    Read against the foreign-window control, never alone: a level-2 summary that opens a lot of
    generic threads will "retain" subjects it never saw, and the only way to see that is to score
    it against a window it did not read.
    """
    wanted: set[str] = set()
    for part in parts:
        wanted |= set(part["promises_opened"])
    if not wanted:
        return float("nan")
    carried = set(whole["promises_opened"]) | set(whole["characters_tokens"])
    hits = sum(1 for subject in wanted if subject in carried or _overlaps(subject, carried))
    return hits / len(wanted)


def _overlaps(subject: str, carried: set[str]) -> bool:
    """A multi-word subject counts as carried when any of its content words survives.

    Loose on purpose, and in the direction that *hurts* the claim: a permissive match inflates both
    the real retention and the foreign-window control, and the condition is stated on their
    difference. A strict match would let a paraphrase read as drift.
    """
    words = set(subject.split())
    return bool(words & carried)


# ------------------------------------------------------------------------------------ the calls


def _synthetic_summary(key: str) -> str:
    """A dry run's stand-in, drawn from the request digest and carrying **no** scene signal.

    Same discipline as `elicit._synthetic_text`: the answer ignores the scene entirely, so a dry run
    is a draw from the null and every statistic below should read as nothing — separation near zero,
    ICC near zero, retention indistinguishable from its foreign control. Synthesising a plausible
    summary would make the pipeline's first real run also its first integration test.
    """
    seed = int(digest(key)[:8], 16)
    cast = ["mira", "the courier", "vel", "the toll-keeper", "anneke"]
    who = sorted({cast[seed % 5], cast[(seed // 5) % 5]})
    opened = [{"subject": f"thread-{(seed // 25) % 7}", "description": "owed"}]
    delta = (
        None
        if seed % 3 == 0
        else {"who": who[0], "what_changed": "standing", "from": "held", "to": "spent"}
    )
    return json.dumps(
        {
            "setting": "a room, after dark",
            "characters": ", ".join(who),
            "events": "words were exchanged and one of them left",
            "open": "what the other one meant by it",
            "delta": delta,
            "promises_opened": opened,
            "promises_paid": [] if seed % 2 else [f"thread-{(seed // 175) % 7}"],
        }
    )


def summarise_once(
    elicitor: Elicitor,
    text: str,
    *,
    unit_id: str,
    sample: int,
    model: str,
    level: int,
    effort: str | None,
) -> dict[str, Any] | None:
    """One call through the shipped prompt and schema. `None` when nothing parseable came back.

    Imported lazily for the reason `corpus_io` gives: this module is run by interpreters that do not
    have the package installed, and only this function needs it.
    """
    from litharness.application.summarize import SUMMARY_SCHEMA, render_summary_prompt

    system, prompt = render_summary_prompt(text)
    params: dict[str, Any] = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": system,
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        "output_config": {"format": {"type": "json_schema", "schema": SUMMARY_SCHEMA}},
    }
    if effort is not None:
        params["output_config"]["effort"] = effort
    tag = {"unit": unit_id, "level": level, "stage": "summary", "sample": sample}
    if elicitor.dry_run:
        key = f"{digest({'params': params, 'transport': elicitor.transport})}:{sample}"
        record: dict[str, Any] = {
            **tag,
            "key": key,
            "model": model,
            "text": _synthetic_summary(key),
            "refused": False,
            "usage": {},
            "dry_run": True,
        }
    else:
        # `_call` rather than a public entry point on purpose: everything public on `Elicitor`
        # takes a `Persona` and renders `personas.system_prompt`, and the whole point here is to
        # send the *shipped* summariser prompt unaltered. `_call` is the transport-and-cache
        # primitive underneath that, and it is what makes the digest cache, the refusal record,
        # and the JSONL resume apply to these calls identically to every persona call.
        record = elicitor._call(params, sample=sample, tag=tag)
    if record.get("refused") or not record.get("text"):
        return None
    try:
        decoded = json.loads(record["text"])
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, dict) else None


def render_level2_input(summaries: list[dict[str, Any]]) -> str:
    """A window of level-1 summaries, laid out as the prose a level-2 call would read.

    This is where the level-2 arm stops measuring a shipped thing. No such rendering exists in the
    system — `context.py` evicts summaries rather than folding them — so the layout below is a
    proposal's first draft, and its wording is a free parameter the measurement cannot separate
    from the summariser's own behaviour. It is kept deliberately plain for that reason.
    """
    blocks = []
    for index, summary in enumerate(summaries, start=1):
        opened = summary.get("promises_opened") or []
        subjects = ", ".join(
            str(item.get("subject", "")) for item in opened if isinstance(item, dict)
        )
        blocks.append(
            f"Scene {index}.\n"
            f"Setting: {summary.get('setting', '')}\n"
            f"Characters: {summary.get('characters', '')}\n"
            f"Events: {summary.get('events', '')}\n"
            f"Left open: {summary.get('open', '')}\n"
            f"Threads opened: {subjects or 'none'}"
        )
    return "\n\n".join(blocks)


# ------------------------------------------------------------------------------------- the run


def load_units(args: argparse.Namespace) -> tuple[list[Unit], str]:
    """Scenes and an honest label for where they came from.

    Total by construction — a source that is not one of these raises rather than falling through to
    a default. `persona_battery.source_label` earned that rule the hard way: a fall-through default
    labelled generated prose as `published` for a whole run.
    """
    if args.book_db:
        units = generated_scenes(
            args.book_db, book=args.book, branch=args.branch, min_words=args.min_words
        )
        return units[: args.scenes], "generated"
    if args.fixtures:
        return fixture_scenes()[: args.scenes], "fixtures"
    raise SystemExit("choose a source: --book-db PATH or --fixtures")


def verdict(report: dict[str, Any]) -> dict[str, object]:
    """The pre-registered conditions, read in order, with every failure named."""
    failures: list[str] = []
    passes: list[str] = []

    identity = report["level1"]["sets"]["characters"]["separation"]
    (passes if identity >= 0.30 else failures).append(f"identity {identity:+.4f}")

    for key, field in (("ledger", "n_promises_opened"), ("delta", "delta_present")):
        entry = report["level1"]["numeric"][field]
        if entry.get("status") != "measured":
            failures.append(f"{key} {entry.get('status')}")
            continue
        value = float(entry["icc1"])
        label = f"{key} ICC {value:.4f}"
        (passes if not math.isnan(value) and value >= 0.50 else failures).append(label)

    constants = [
        field
        for field in NUMERIC_FIELDS
        if report["level1"]["numeric"][field].get("status") == "constant"
    ]
    if constants:
        failures.append("positivity FIRED on " + ", ".join(constants))
    else:
        passes.append("positivity clear")

    return {
        "verdict": "DEAD" if failures else "SURVIVES",
        "failed": failures,
        "passed": passes,
        "conditions": PRE_REGISTRATION,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    units, source = load_units(args)
    if len(units) < 2:
        raise SystemExit(
            f"need at least 2 scenes to have a between-scene contrast, got {len(units)}"
        )

    planned = len(units) * args.samples
    windows: list[list[Unit]] = []
    if args.level >= 2:
        windows = [
            units[start : start + args.window]
            for start in range(0, len(units) - args.window + 1, args.window)
        ]
        planned += len(windows) * args.samples
    if planned > CALL_GUARD and not args.yes and not args.dry_run:
        raise SystemExit(f"{planned} calls exceeds the {CALL_GUARD} guard; pass --yes to mean it")

    report: dict[str, Any] = {
        "source": source,
        "model": args.model,
        "transport": args.transport,
        "effort": args.effort,
        "scenes": [unit.unit_id for unit in units],
        "samples": args.samples,
        "planned_calls": planned,
    }

    with Elicitor(
        Path(args.cache),
        model=args.model,
        spot_model=None,
        spot_fraction=0.0,
        effort=args.effort,
        transport=args.transport,
        dry_run=args.dry_run,
    ) as elicitor:
        per_scene: dict[str, list[dict[str, Any]]] = {}
        raw_scene: dict[str, list[dict[str, Any]]] = {}
        unparsed = 0
        for unit in units:
            rows: list[dict[str, Any]] = []
            raws: list[dict[str, Any]] = []
            for sample in range(args.samples):
                summary = summarise_once(
                    elicitor,
                    unit.text,
                    unit_id=unit.unit_id,
                    sample=sample,
                    model=args.model,
                    level=1,
                    effort=args.effort,
                )
                if summary is None:
                    unparsed += 1
                    continue
                rows.append(features(summary))
                raws.append(summary)
            if len(rows) >= 2:
                per_scene[unit.unit_id] = rows
                raw_scene[unit.unit_id] = raws

        report["level1"] = {
            "unparsed": unparsed,
            "scenes_usable": len(per_scene),
            "numeric": {field: numeric_report(per_scene, field) for field in NUMERIC_FIELDS},
            "sets": {
                field: separation(per_scene, field)
                for field in (*SET_FIELDS, "characters_tokens")
            },
        }
        report["ladder"] = verdict(report)

        if args.level >= 2 and windows:
            report["level2"] = _run_level2(elicitor, args, windows, raw_scene)
            report["level2"]["gated_by"] = report["ladder"]["verdict"]

        report["spend"] = elicitor.spend()
        report["api_calls"] = elicitor.api_calls
        report["replayed"] = elicitor.replayed
    return report


def _run_level2(
    elicitor: Elicitor,
    args: argparse.Namespace,
    windows: list[list[Unit]],
    raw_scene: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Summaries of summaries, and the foreign-window control that makes retention readable."""
    per_window: dict[str, list[dict[str, Any]]] = {}
    window_parts: dict[str, list[dict[str, Any]]] = {}
    skipped: list[str] = []
    for index, window in enumerate(windows):
        parts = [raw_scene[unit.unit_id][0] for unit in window if unit.unit_id in raw_scene]
        if len(parts) < args.window:
            skipped.append(f"w{index}")
            continue
        window_id = f"w{index}"
        window_parts[window_id] = [features(part) for part in parts]
        text = render_level2_input(parts)
        rows: list[dict[str, Any]] = []
        for sample in range(args.samples):
            summary = summarise_once(
                elicitor,
                text,
                unit_id=window_id,
                sample=sample,
                model=args.model,
                level=2,
                effort=args.effort,
            )
            if summary is not None:
                rows.append(features(summary))
        if len(rows) >= 2:
            per_window[window_id] = rows

    result: dict[str, Any] = {
        "windows": len(per_window),
        "window_size": args.window,
        "skipped": skipped,
        "note": "no shipped level-2 path exists; context.py evicts. See render_level2_input.",
    }
    if len(per_window) >= 2:
        result["numeric"] = {field: numeric_report(per_window, field) for field in NUMERIC_FIELDS}
        result["sets"] = {
            field: separation(per_window, field) for field in (*SET_FIELDS, "characters_tokens")
        }

    own: list[float] = []
    foreign: list[float] = []
    window_ids = sorted(per_window)
    for window_id in window_ids:
        for row in per_window[window_id]:
            value = retention(window_parts[window_id], row)
            if not math.isnan(value):
                own.append(value)
            for other in window_ids:
                if other == window_id:
                    continue
                control = retention(window_parts[other], row)
                if not math.isnan(control):
                    foreign.append(control)
    own_mean = statistics.fmean(own) if own else float("nan")
    foreign_mean = statistics.fmean(foreign) if foreign else float("nan")
    gap = own_mean - foreign_mean
    result["retention"] = {
        "own": round(own_mean, 4) if not math.isnan(own_mean) else float("nan"),
        "foreign": round(foreign_mean, 4) if not math.isnan(foreign_mean) else float("nan"),
        "gap": round(gap, 4) if not math.isnan(gap) else float("nan"),
        "drift": round(1.0 - own_mean, 4) if not math.isnan(own_mean) else float("nan"),
        "n_own": len(own),
        "n_foreign": len(foreign),
        "condition": PRE_REGISTRATION["level2"],
    }
    return result


# ------------------------------------------------------------------------------------ selftest


def selftest() -> None:
    """Arithmetic checks that need no transport. Every one of these has a bug behind it."""
    assert jaccard(frozenset(), frozenset()) == 1.0
    assert jaccard(frozenset({"a"}), frozenset()) == 0.0
    assert jaccard(frozenset({"a", "b"}), frozenset({"b", "c"})) == 1 / 3

    assert _name_set("Mira, the toll-keeper and Vel") == frozenset({"mira", "toll keeper", "vel"})
    assert _name_set([{"subject": "The Debt"}, {"subject": "debt"}]) == frozenset({"debt"})

    ideal = features(
        {
            "setting": "a",
            "characters": "Mira and Vel",
            "events": "b",
            "open": "c",
            "delta": {"who": "Mira", "what_changed": "trust", "from": "x", "to": "y"},
            "promises_opened": [{"subject": "the debt", "description": "d"}],
            "promises_paid": ["an older debt"],
        }
    )
    assert ideal["delta_present"] == 1.0
    assert ideal["n_characters"] == 2.0
    assert ideal["n_promises_opened"] == 1.0

    # A delta object with an empty `what_changed` is an absent delta, not a present one: the schema
    # lets the model fill the shape without answering, and counting the shape would read a
    # formatting habit as a dramatic shift.
    empty_delta = {"who": "", "what_changed": "", "from": "", "to": ""}
    assert features({"delta": empty_delta})["delta_present"] == 0.0

    # Perfect within-unit agreement and total between-unit disagreement is the separation ceiling.
    left = [features({"characters": "Mira"}), features({"characters": "Mira"})]
    right = [features({"characters": "Vel"}), features({"characters": "Vel"})]
    split = separation({"a": left, "b": right}, "characters")
    assert split["within"] == 1.0
    assert split["between"] == 0.0
    assert split["separation"] == 1.0

    # And the degenerate field the empty-set convention would otherwise flatter: identical
    # everywhere scores 1.0 within *and* 1.0 between, so the separation is zero.
    flat = {"a": [features({}), features({})], "b": [features({}), features({})]}
    assert separation(flat, "promises_paid")["separation"] == 0.0

    constant = numeric_report({"a": [{"x": 1.0}, {"x": 1.0}], "b": [{"x": 1.0}]}, "x")
    assert constant["status"] == "constant"

    varied = numeric_report({"a": [{"x": 1.0}, {"x": 1.1}], "b": [{"x": 5.0}, {"x": 5.1}]}, "x")
    assert varied["status"] == "measured"
    assert float(str(varied["icc1"])) > 0.9

    parts = [features({"promises_opened": [{"subject": "the debt"}]})]
    whole = features({"characters": "the debt is owed", "promises_opened": []})
    assert retention(parts, whole) == 1.0
    assert math.isnan(retention([features({})], whole))

    print("summary_reliability selftest OK")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--book-db", help="sqlite book database; read through export.collect")
    parser.add_argument("--book")
    parser.add_argument("--branch")
    parser.add_argument("--min-words", type=int, default=200)
    parser.add_argument("--fixtures", action="store_true", help="the bundled fixture story instead")
    parser.add_argument("--scenes", type=int, default=10)
    parser.add_argument("--samples", type=int, default=5, help="byte-identical re-samples per unit")
    parser.add_argument("--level", type=int, default=1, choices=(1, 2))
    parser.add_argument("--window", type=int, default=3, help="level-1 summaries per level-2 call")
    parser.add_argument("--model", default=PANEL_MODEL)
    parser.add_argument("--effort", default=None)
    parser.add_argument("--transport", default="cli", choices=("cli", "sdk", "ollama"))
    parser.add_argument("--cache", default=str(HERE / "results" / "summary-reliability-raw.jsonl"))
    parser.add_argument("--out", default=str(HERE / "results" / "summary-reliability.json"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        selftest()
        return 0

    report = run(args)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report["ladder"], indent=2))
    print(json.dumps(report["level1"]["sets"]["characters"], indent=2))
    if "level2" in report:
        print(json.dumps(report["level2"].get("retention", {}), indent=2))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
