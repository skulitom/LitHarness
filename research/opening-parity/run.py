"""Opening parity: our chapter-1 openings beside the market's summits, on the frozen panel.

`PREREG.md` beside this file is the registration and owns every number in it. This driver
reuses `house_panel.py` wholesale — its blinded `Side`, its ten-persona x both-orders cell,
its paid loop, its result payload and its refusals — and adds only what a many-pair run
needs: stimulus construction for two arms, the recognition probes in front of every stimulus,
a fixed pair plan, one shared cache, and a summary a person reads.

Two arms, two stimulus shapes:

- `opening` — the first `OPENING_WORDS` words of chapter 1, extended to the paragraph
  boundary (`blinding.first_words`), then blinded. Length-matched by construction.
- `listing` — the blurb, a blank line, then the first `LISTING_WORDS` words of chapter 1: the
  backtest's P-arm shape byte for byte. A stimulus without a blurb on disk is not built.

Everything this module writes is counts, shares, digests and labels. No stimulus text lands
in any result file; the stimulus files themselves are written under `runs/` (gitignored) so
a person can open what a persona was shown. Nothing here gates, ranks, promotes, or reaches
a prompt, and `house_panel.write_result` refuses any payload naming a verdict or a score.

Run (both ceilings are required, as `house_panel` requires them):

    uv run python research/opening-parity/run.py --manifest research/opening-parity/manifest.json \
        --max-usd 100 --max-sessions 1100

`--dry-run` builds the stimuli, prints the plan and the cost note, and constructs no elicitor.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import threading
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
for sibling in (REPO_ROOT / "research" / "sim-readership-backtest",
                REPO_ROOT / "research" / "quality-measurement"):
    if str(sibling) not in sys.path:
        sys.path.insert(0, str(sibling))

import backtest  # noqa: E402  # sibling research module, imported by path
import blinding  # noqa: E402
import house_panel  # noqa: E402
import population  # noqa: E402
import recognition  # noqa: E402

#: The opening arm's cut, in words, extended to the paragraph boundary. Chosen so every
#: stimulus on the manifest — ours at ~2,000 words, the anchors at ~1,600 — is cut rather
#: than shown whole, which is what makes the arm length-matched.
OPENING_WORDS = 1500

#: The listing arm's chapter-1 window: `arms.PREMISE_WORDS`, restated so this file can be
#: read on its own. A different number here would be a different instrument.
LISTING_WORDS = 500

ARMS: tuple[str, ...] = ("opening", "listing")

#: The probes' truth window and answer cap, as `backtest` runs them.
TRUTH_WORDS = 80
PROBE_MAX_TOKENS = 80

#: Pooled first-slot share outside this band is reported as a void reading for the arm (the
#: §120 precedent). Reported, never corrected for.
POSITIONAL_BAND = (0.35, 0.65)

#: How far past its cut a stimulus may run before it is refused as not length-matched. The
#: paragraph holding the cut word is shown whole, so a normal chapter overshoots by one
#: paragraph; a text with no paragraph breaks at all overshoots by the rest of the chapter.
#: Measured on the first dry run: one shard chapter arrived as a single 2,838-word paragraph,
#: and the arm would have shown a persona one side at nearly twice the other's length.
OVERSHOOT_RATIO = 1.25

_DEFAULT_MODEL = house_panel._DEFAULT_MODEL
_DEFAULT_OUT = REPO_ROOT / "runs" / "opening-parity"


# ------------------------------------------------------------------------------- the stimuli


@dataclass(frozen=True, slots=True)
class Entry:
    """One manifest row: a chapter file, an optional blurb file, and what to blind out.

    A row under `controls` names `shuffle_of`: its stimulus is another entry's chapter with
    its paragraphs in a seeded random order — the backtest's damage arm, brought here so a
    preference for one of our openings over a summit can be asked whether it survives the
    story being taken out of the text. A control never enters the ours x summit product; it is
    paired only where the manifest's calibration list names it.
    """

    label: str
    side: str  # "ours" | "summit" | "control"
    chapter: Path
    blurb: Path | None
    title: str
    author: str
    shuffle_of: str | None = None
    shuffle_seed: int = 0
    #: Whether an `ours` entry enters the ours x summit product. `False` keeps it on the
    #: manifest for calibration pairs only (PREREG §5c cut the product to two of ours after
    #: three pairs had read the same way); a summit ignores the field.
    in_product: bool = True

    @classmethod
    def from_row(cls, row: Mapping[str, Any], side: str, root: Path) -> Entry:
        blurb = row.get("blurb")
        return cls(
            label=str(row["label"]),
            side=side,
            chapter=root / str(row["chapter"]),
            blurb=(root / str(blurb)) if blurb else None,
            title=str(row.get("title") or ""),
            author=str(row.get("author") or ""),
            shuffle_of=(str(row["shuffle_of"]) if row.get("shuffle_of") else None),
            shuffle_seed=int(row.get("shuffle_seed") or 0),
            in_product=bool(row.get("in_product", True)),
        )


@dataclass(frozen=True, slots=True)
class Stimulus:
    """One arm's stimulus for one entry: the blinded text on disk, and the probe's truth."""

    arm: str
    entry: Entry
    path: Path
    text: str
    digest: str
    words: int
    truth: str

    @property
    def label(self) -> str:
        return self.entry.label


def _read(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        raise house_panel.ForbiddenOutput(f"{path} is empty; an empty stimulus is not a stimulus")
    return _paragraphed(raw)


def _shuffled(text: str, seed: int) -> str:
    """The text's paragraphs in a seeded random order; a one-paragraph text is unchanged.

    `random.Random(seed)` rather than the module-level generator, so the permutation depends
    on the seed and the paragraph count alone and every run of the same manifest shows a
    persona the same control.
    """
    import random

    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) < 2:
        return text
    order = list(range(len(paragraphs)))
    random.Random(seed).shuffle(order)
    if order == list(range(len(paragraphs))):
        order = order[1:] + order[:1]
    return "\n\n".join(paragraphs[i] for i in order)


def _paragraphed(raw: str) -> str:
    """A text whose paragraphs are separated by single newlines, re-separated by blank lines.

    Every cut in this driver lands on a paragraph boundary, and `blinding.first_words` reads a
    boundary as a blank line. A chapter saved with one newline per paragraph and no blank
    lines at all — *The Gam3*'s file as placed on the shelf — would therefore be shown whole
    and refused as not length-matched. A file that already has blank lines is returned
    untouched, so nothing already measured moves; a file with no newlines at all is returned
    untouched too, and the overshoot guard refuses it as before.
    """
    if "\n\n" in raw or "\n" not in raw.strip():
        return raw
    return re.sub(r"\n+", "\n\n", raw.strip()) + "\n"


def build_stimulus(entry: Entry, arm: str, out_dir: Path) -> Stimulus | None:
    """The stimulus for `entry` in `arm`, written under `out_dir`; `None` when it cannot be built.

    The only case that returns `None` is a listing-arm entry with no blurb on disk. That is a
    refusal to fabricate a stimulus, not a degraded one: PREREG §2 says why the two anchors sit
    out of the listing arm until their blurbs exist.
    """
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}; arms are {ARMS}")
    raw = _read(entry.chapter)
    cut = OPENING_WORDS if arm == "opening" else LISTING_WORDS
    excerpt = blinding.first_words(raw, cut)
    if entry.shuffle_of is not None:
        # The damage control: the SAME cut as the source, then its paragraphs in a seeded
        # random order, so the two stimuli hold the same words and differ only in whether the
        # story is in order. The seed is in the manifest and the result file, so the shuffle
        # is one fixed permutation and not a fresh coin per run.
        excerpt = _shuffled(excerpt, entry.shuffle_seed)
    if len(excerpt.split()) > cut * OVERSHOOT_RATIO:
        raise house_panel.ForbiddenOutput(
            f"{entry.chapter}: no paragraph boundary near the {cut}-word cut "
            f"({len(excerpt.split())} words shown); the arm is length-matched or it is not run"
        )
    if arm == "opening":
        shown = excerpt
    else:
        if entry.blurb is None:
            return None
        blurb = _read(entry.blurb).strip()
        shown = f"{blurb}\n\n{excerpt}"
    rest = raw[len(excerpt):] if raw.startswith(excerpt) else ""
    truth = " ".join(rest.split()[:TRUTH_WORDS])
    blinded = blinding.blind(shown, title=entry.title, author=entry.author)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{arm}-{entry.label}.txt"
    path.write_text(blinded.text, encoding="utf-8", newline="\n")
    return Stimulus(
        arm=arm, entry=entry, path=path, text=blinded.text, digest=blinded.digest,
        words=len(blinded.text.split()), truth=truth,
    )


def build_all(manifest: Mapping[str, Any], root: Path, out_dir: Path,
              arms: Sequence[str] = ARMS) -> dict[str, dict[str, Stimulus]]:
    """Every stimulus for every arm, keyed arm -> label. Entries without a blurb skip `listing`."""
    entries = [Entry.from_row(row, "ours", root) for row in manifest["ours"]]
    entries += [Entry.from_row(row, "summit", root) for row in manifest["summits"]]
    by_label = {entry.label: entry for entry in entries}
    for row in manifest.get("controls", []):
        source = by_label.get(str(row.get("shuffle_of") or ""))
        if source is None:
            raise ValueError(f"control {row.get('label')!r} shuffles an entry the manifest lacks")
        # A control is the source's chapter and blurb, cut and blinded as the source is, with
        # only the paragraph order changed — so it inherits the source's files and identity.
        entries.append(
            Entry(
                label=str(row["label"]), side="control", chapter=source.chapter,
                blurb=source.blurb, title=source.title, author=source.author,
                shuffle_of=source.label, shuffle_seed=int(row.get("shuffle_seed") or 0),
            )
        )
    labels = [entry.label for entry in entries]
    if len(set(labels)) != len(labels):
        raise ValueError(f"manifest labels must be unique; got {labels}")
    calibration = manifest.get("calibration", {})
    built: dict[str, dict[str, Stimulus]] = {}
    for arm in arms:
        built[arm] = {}
        named = {label for pair in calibration.get(arm, []) for label in pair}
        for entry in entries:
            # A control exists only in an arm whose calibration list names it: it is never in
            # the product, so building it elsewhere would probe and cut a stimulus nothing
            # ever shows.
            if entry.side == "control" and entry.label not in named:
                continue
            stimulus = build_stimulus(entry, arm, out_dir / "stimuli")
            if stimulus is not None:
                built[arm][entry.label] = stimulus
    return built


# ------------------------------------------------------------------------------- the pair plan


@dataclass(frozen=True, slots=True)
class PairSpec:
    arm: str
    label_a: str
    label_b: str
    kind: str  # "ours-vs-summit" | "summit-vs-summit" | "ours-vs-ours"


def plan_pairs(manifest: Mapping[str, Any], built: Mapping[str, Mapping[str, Stimulus]],
               arms: Sequence[str] = ARMS) -> list[PairSpec]:
    """Every (ours x summit) pair per arm, then the manifest's calibration pairs. Fixed before
    any call; nothing selects among our openings on a result."""
    pairs: list[PairSpec] = []
    calibration = manifest.get("calibration", {})
    for arm in arms:
        have = built[arm]
        ours = [s for s in have.values() if s.entry.side == "ours" and s.entry.in_product]
        summits = [s for s in have.values() if s.entry.side == "summit"]
        # **Calibration and control pairs first, the product after** (2026-09-01, after the
        # product's first ten pairs all read one way): the pairs that decide how a product
        # share is read are the ones a person needs earliest, and buying order changes nothing
        # about any cell — pair ids are content-addressed and every cell replays.
        product = [
            PairSpec(arm, mine.label, summit.label, "ours-vs-summit")
            for mine in ours
            for summit in summits
        ]
        for label_a, label_b in calibration.get(arm, []):
            if label_a not in have or label_b not in have:
                continue
            side_a, side_b = have[label_a].entry.side, have[label_b].entry.side
            sides = {side_a, side_b}
            if "control" in sides:
                kind = "control-vs-source" if sides == {"control", "ours"} else (
                    "control-vs-summit" if "summit" in sides else "control-vs-control"
                )
            elif sides == {"ours"}:
                kind = "ours-vs-ours"
            elif sides == {"summit"}:
                kind = "summit-vs-summit"
            else:
                kind = "ours-vs-summit"
            pairs.append(PairSpec(arm, label_a, label_b, kind))
        pairs.extend(product)
    return pairs


def sessions_per_pair() -> int:
    return len(population.POPULATION) * 2


# ------------------------------------------------------------------------------- the probes


def _sample(payload: str) -> int:
    return int(hashlib.sha256(payload.encode()).hexdigest()[:16], 16)


def probe_stimulus(elicitor: house_panel.Elicits, stimulus: Stimulus, *, model: str
                   ) -> dict[str, Any]:
    """`backtest.probe_book`'s three probes, over one stimulus, classified the same way.

    A probe the transport did not answer classifies the stimulus `unprobed`, never `clean` —
    the rule `backtest.probe_book` earned on the 2026-08-30 pilot, kept here verbatim.
    """
    results: list[recognition.ProbeResult] = []
    unanswered: list[str] = []
    for index, (probe_name, template) in enumerate(recognition.PROBES):
        record = elicitor.ask_raw(
            "", [{"role": "user", "content": template.format(excerpt=stimulus.text)}],
            schema=None, max_tokens=PROBE_MAX_TOKENS,
            tag={"stage": "probe", "probe": probe_name,
                 "stimulus": f"{stimulus.arm}:{stimulus.label}"},
            sample=_sample(f"opening-parity|probe|{stimulus.arm}|{stimulus.label}|{index}"),
            model=model,
        )
        answer = record.get("text") or ""
        if not answer.strip():
            unanswered.append(probe_name)
        results.append(
            recognition.score_probe(
                probe_name, answer, title=stimulus.entry.title,
                author=stimulus.entry.author, truth_continuation=stimulus.truth,
            )
        )
    classification = "unprobed" if unanswered else recognition.classify(results)
    return {
        "arm": stimulus.arm,
        "label": stimulus.label,
        "side": stimulus.entry.side,
        "classification": classification,
        "hits": [r.probe for r in results if r.hit],
        "unanswered": unanswered,
        "digest": stimulus.digest,
        "words": stimulus.words,
        "shuffle_of": stimulus.entry.shuffle_of,
        "shuffle_seed": stimulus.entry.shuffle_seed if stimulus.entry.shuffle_of else None,
    }


# ------------------------------------------------------------------------------- the paid loop


@dataclass(slots=True)
class PairOutcome:
    spec: PairSpec
    answers: list[house_panel.PanelAnswer]
    result: dict[str, Any]
    planned: int
    aborted: bool
    refused: str | None = None


def run_pair(elicitor: house_panel.Elicits, spec: PairSpec,
             built: Mapping[str, Mapping[str, Stimulus]], *, model: str, max_usd: float,
             max_sessions: int, out_dir: Path) -> PairOutcome:
    """One pair through `house_panel`'s own plan → run → build → write, with its own file."""
    stim_a = built[spec.arm][spec.label_a]
    stim_b = built[spec.arm][spec.label_b]
    side_a = house_panel.read_side(
        stim_a.path, label=spec.label_a, title=stim_a.entry.title, author=stim_a.entry.author
    )
    side_b = house_panel.read_side(
        stim_b.path, label=spec.label_b, title=stim_b.entry.title, author=stim_b.entry.author
    )
    try:
        planned = house_panel.plan_sessions(side_a, side_b)
    except backtest.DegenerateStimuli as refusal:
        return PairOutcome(spec, [], {}, 0, False, refused=str(refusal))
    ledger: dict[str, float] = {"equivalent_usd": 0.0}
    answers, aborted = house_panel.run_panel(
        elicitor, planned, model=model, ledger=ledger, max_usd=max_usd
    )
    result = house_panel.build_result(
        side_a, side_b, planned, answers, model=model, ledger=ledger, max_usd=max_usd,
        max_sessions=max_sessions, aborted=aborted, elicitor=elicitor,
    )
    result["pair"] = {
        "arm": spec.arm, "kind": spec.kind, "file_a": spec.label_a, "file_b": spec.label_b,
    }
    path = out_dir / spec.arm / f"pair-{spec.label_a}--{spec.label_b}.json"
    house_panel.write_result(result, path)
    return PairOutcome(spec, answers, result, len(planned), aborted)


# ------------------------------------------------------------------------------- the summary


def _share(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0.0


def _pool(outcomes: Sequence[PairOutcome], *, ours_is: str) -> dict[str, Any]:
    """Pooled counts over pairs, in file space, with `ours` named as the side given."""
    ours = neither = decided = returned = first_slot = 0
    for outcome in outcomes:
        for answer in outcome.answers:
            returned += 1
            choice = answer.file_choice
            if choice == "neither":
                neither += 1
                continue
            decided += 1
            if answer.choice == "A":
                first_slot += 1
            if choice == ours_is:
                ours += 1
    return {
        "pairs": len(outcomes),
        "returned": returned,
        "decided": decided,
        "neither": neither,
        "ours_chosen": ours,
        "ours_share_of_decided": _share(ours, decided),
        "first_slot_share": _share(first_slot, decided),
    }


def summarize(outcomes: Sequence[PairOutcome], probes: Sequence[Mapping[str, Any]],
              *, model: str, ledger_usd: float) -> dict[str, Any]:
    """Counts and shares a person reads; every block carries `exploratory: true`."""
    recognised = {
        (p["arm"], p["label"]) for p in probes if p["classification"] != "clean"
    }
    by_arm: dict[str, Any] = {}
    for arm in ARMS:
        arm_outcomes = [o for o in outcomes if o.spec.arm == arm and o.refused is None]
        if not arm_outcomes:
            continue
        rows = []
        for o in arm_outcomes:
            agg = o.result["shares"]["aggregate"]
            rows.append({
                "file_a": o.spec.label_a, "file_b": o.spec.label_b, "kind": o.spec.kind,
                "returned": agg["returned"], "decided": agg["decided"],
                "neither": agg["neither"],
                "file_a_share_of_decided": agg["share_of_decided"]["file_a"],
                "first_slot_share": o.result["positional"]["first_slot_share"],
                "aborted_at_ceiling": o.aborted,
                "stratum": (
                    "recognised"
                    if (arm, o.spec.label_a) in recognised or (arm, o.spec.label_b) in recognised
                    else "clean"
                ),
            })
        versus = [o for o in arm_outcomes if o.spec.kind == "ours-vs-summit"]
        clean = [o for o in versus if (arm, o.spec.label_b) not in recognised]
        recog = [o for o in versus if (arm, o.spec.label_b) in recognised]
        by_ours = {
            label: _pool([o for o in versus if o.spec.label_a == label], ours_is="file_a")
            for label in sorted({o.spec.label_a for o in versus})
        }
        by_summit = {
            label: _pool([o for o in versus if o.spec.label_b == label], ours_is="file_a")
            for label in sorted({o.spec.label_b for o in versus})
        }
        pooled = _pool(versus, ours_is="file_a")
        low, high = POSITIONAL_BAND
        void = pooled["decided"] > 0 and not (low <= pooled["first_slot_share"] <= high)
        codes: dict[str, int] = {}
        for o in arm_outcomes:
            for code, count in o.result["reason_codes"]["counts"].items():
                codes[code] = codes.get(code, 0) + int(count)
        by_arm[arm] = {
            house_panel.LABEL: True,
            "pairs": rows,
            "ours_vs_summit_pooled": pooled,
            "ours_vs_summit_clean_stratum": _pool(clean, ours_is="file_a"),
            "ours_vs_summit_recognised_stratum": _pool(recog, ours_is="file_a"),
            "by_ours": by_ours,
            "by_summit": by_summit,
            "calibration": {
                kind: _pool([o for o in arm_outcomes if o.spec.kind == kind], ours_is="file_a")
                for kind in (
                    "summit-vs-summit", "ours-vs-ours", "control-vs-summit",
                    "control-vs-source", "control-vs-control",
                )
            },
            "positional_void_reading": void,
            "positional_band": list(POSITIONAL_BAND),
            "reason_codes": codes,
        }
    refused = [
        {"arm": o.spec.arm, "file_a": o.spec.label_a, "file_b": o.spec.label_b,
         "refused": o.refused}
        for o in outcomes if o.refused is not None
    ]
    return {
        house_panel.LABEL: True,
        "provenance": house_panel.PROVENANCE,
        "reads": "one person; nothing downstream consumes this file",
        "registration": "research/opening-parity/PREREG.md",
        "panel": {
            "model": model,
            "population_digest": population.population_digest(),
            "personas": len(population.POPULATION),
            "orders": [0, 1],
            "opening_words": OPENING_WORDS,
            "listing_words": LISTING_WORDS,
        },
        "probes": list(probes),
        "arms": by_arm,
        "refused_pairs": refused,
        "cost": {
            "sessions_planned": sum(o.planned for o in outcomes),
            "usd_per_session_basis": house_panel.USD_PER_SESSION,
            "ledger_usd_cumulative_over_cache": round(ledger_usd, 4),
        },
    }


def render_markdown(summary: Mapping[str, Any]) -> str:
    """A table per arm, counts and shares only. Labels are ours; no stimulus text appears."""
    lines = ["# Opening parity — summary", "", f"> {summary['provenance']}", ""]
    for arm, block in summary["arms"].items():
        lines += [f"## Arm `{arm}`", "",
                  "| file A (ours or summit) | file B | kind | stratum | decided | neither | "
                  "A share of decided | first-slot share |",
                  "| --- | --- | --- | --- | --: | --: | --: | --: |"]
        for row in block["pairs"]:
            lines.append(
                f"| {row['file_a']} | {row['file_b']} | {row['kind']} | {row['stratum']} | "
                f"{row['decided']} | {row['neither']} | {row['file_a_share_of_decided']} | "
                f"{row['first_slot_share']} |"
            )
        pooled = block["ours_vs_summit_pooled"]
        lines += ["", f"Pooled ours-vs-summit: ours chosen {pooled['ours_chosen']} of "
                  f"{pooled['decided']} decided ({pooled['ours_share_of_decided']}), "
                  f"neither {pooled['neither']}, first-slot share "
                  f"{pooled['first_slot_share']}"
                  + (" — VOID READING (positional)" if block["positional_void_reading"] else ""),
                  ""]
        for name, pool in (("clean stratum", block["ours_vs_summit_clean_stratum"]),
                           ("recognised stratum", block["ours_vs_summit_recognised_stratum"])):
            lines.append(f"- {name}: ours {pool['ours_chosen']} of {pool['decided']} decided "
                         f"({pool['ours_share_of_decided']}) over {pool['pairs']} pair(s)")
        lines.append("- by ours: " + ", ".join(
            f"{label} {p['ours_chosen']}/{p['decided']}" for label, p in block["by_ours"].items()
        ))
        lines.append("- by summit: " + ", ".join(
            f"{label} {p['decided'] - p['ours_chosen']}/{p['decided']} for the summit"
            for label, p in block["by_summit"].items()
        ))
        for kind, pool in block["calibration"].items():
            lines.append(f"- calibration {kind}: file A {pool['ours_chosen']} of "
                         f"{pool['decided']} decided over {pool['pairs']} pair(s)")
        lines.append("- reason codes: " + ", ".join(
            f"{code or '(none)'} {n}" for code, n in block["reason_codes"].items() if n
        ))
        lines.append("")
    lines += ["## Recognition probes", "", "| arm | stimulus | side | classification | hits |",
              "| --- | --- | --- | --- | --- |"]
    for p in summary["probes"]:
        lines.append(f"| {p['arm']} | {p['label']} | {p['side']} | {p['classification']} | "
                     f"{', '.join(p['hits']) or '-'} |")
    if summary["refused_pairs"]:
        lines += ["", "## Refused pairs", ""]
        lines += [f"- {r['arm']}: {r['file_a']} vs {r['file_b']}: {r['refused']}"
                  for r in summary["refused_pairs"]]
    cost = summary["cost"]
    lines += ["", f"Sessions planned {cost['sessions_planned']}; ledger "
              f"${cost['ledger_usd_cumulative_over_cache']} cumulative over the cache.", ""]
    return "\n".join(lines)


# ------------------------------------------------------------------------------- the CLI


def _default_elicitor(cache: Path, model: str) -> Any:
    """`house_panel._default_elicitor`'s elicitor with one addition: `spend()` under the lock.

    Pairs run on a small thread pool. `Elicitor._call` already takes the instance lock around
    every cache read and write; `spend()` iterates the cache without it, which under
    concurrent appends is a dictionary changing size mid-iteration. Nothing else moves.
    """
    import elicit

    class _LockedElicitor(elicit.Elicitor):
        def spend(self) -> dict[str, int | float]:
            with self._lock:
                return super().spend()

    return _LockedElicitor(cache_path=cache, model=model, spot_model=None, transport="cli")


def main(argv: list[str] | None = None, *, elicitor_factory: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument(
        "--root", default=str(REPO_ROOT),
        help="what the manifest's relative paths are relative to (default: the repository)",
    )
    parser.add_argument("--arms", default=",".join(ARMS))
    parser.add_argument("--model", default=_DEFAULT_MODEL)
    parser.add_argument("--out", default=str(_DEFAULT_OUT))
    parser.add_argument("--cache", default=None, help="default: <out>/panel-cache.jsonl")
    parser.add_argument("--max-usd", type=float, default=None)
    parser.add_argument("--max-sessions", type=int, default=None)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--skip-probes", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = Path(args.root)
    out_dir = Path(args.out)
    arms = tuple(a.strip() for a in args.arms.split(",") if a.strip())
    built = build_all(manifest, root, out_dir, arms)
    pairs = plan_pairs(manifest, built, arms)
    per_pair = sessions_per_pair()
    planned_sessions = per_pair * len(pairs)
    # A control is one of our own openings reordered; recognition is not a question it can be
    # asked, so it is never probed and its source's probe stands for it.
    probed = [
        stimulus for arm in arms for stimulus in built[arm].values()
        if stimulus.entry.side != "control"
    ]
    probe_calls = 0 if args.skip_probes else len(recognition.PROBES) * len(probed)
    print(f"{house_panel.LABEL}: {len(pairs)} pair(s) x {per_pair} sessions = "
          f"{planned_sessions} session(s); {probe_calls} probe call(s)")
    for arm in arms:
        print(f"  {arm}: " + ", ".join(
            f"{s.label}({s.words}w)" for s in built[arm].values()
        ))
    print(house_panel.cost_note(planned_sessions))
    print(f"{house_panel.LABEL}: {house_panel.PROVENANCE}")
    if args.dry_run:
        print(f"{house_panel.LABEL}: dry run — no elicitor constructed, nothing spent",
              file=sys.stderr)
        return 0

    try:
        max_usd = house_panel._ceiling(args.max_usd, house_panel.ENV_MAX_USD, "max_usd")
        max_sessions = int(
            house_panel._ceiling(args.max_sessions, house_panel.ENV_MAX_SESSIONS, "max_sessions")
        )
    except house_panel.CeilingNotExpressed as refusal:
        print(f"{house_panel.LABEL}: refused — {refusal}; nothing was spent", file=sys.stderr)
        return 1
    if planned_sessions > max_sessions:
        print(f"{house_panel.LABEL}: refused — {planned_sessions} planned session(s) exceed "
              f"the ceiling of {max_sessions}; nothing was spent", file=sys.stderr)
        return 1
    if house_panel.estimated_usd(planned_sessions) > max_usd:
        print(f"{house_panel.LABEL}: refused — the estimate exceeds --max-usd; nothing was "
              f"spent", file=sys.stderr)
        return 1

    cache = Path(args.cache) if args.cache else out_dir / "panel-cache.jsonl"
    make_elicitor = elicitor_factory or _default_elicitor
    elicitor = make_elicitor(cache, args.model)

    probes: list[dict[str, Any]] = []
    if not args.skip_probes:
        for stimulus in probed:
            probes.append(probe_stimulus(elicitor, stimulus, model=args.model))
            last = probes[-1]
            print(f"{house_panel.LABEL}: probe {stimulus.arm}:{last['label']} -> "
                  f"{last['classification']} {last['hits']}")

    outcomes: list[PairOutcome] = []
    progress_lock = threading.Lock()

    def one(spec: PairSpec) -> PairOutcome:
        outcome = run_pair(
            elicitor, spec, built, model=args.model, max_usd=max_usd,
            max_sessions=max_sessions, out_dir=out_dir,
        )
        with progress_lock:
            if outcome.refused:
                print(f"{house_panel.LABEL}: {spec.arm} {spec.label_a} vs {spec.label_b}: "
                      f"refused — {outcome.refused}")
            else:
                agg = outcome.result["shares"]["aggregate"]
                print(f"{house_panel.LABEL}: {spec.arm} {spec.label_a} vs {spec.label_b}: "
                      f"A {agg['file_a']} / B {agg['file_b']} / neither {agg['neither']}"
                      + (" (ABORTED at ceiling)" if outcome.aborted else ""))
        return outcome

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        outcomes = list(pool.map(one, pairs))

    spend = elicitor.spend() if hasattr(elicitor, "spend") else {}
    summary = summarize(
        outcomes, probes, model=args.model,
        ledger_usd=float(spend.get("equivalent_usd", 0.0)),
    )
    summary["sessions"] = {
        "transport_failures": getattr(elicitor, "transport_failures", None),
        "fresh_calls": getattr(elicitor, "api_calls", None),
        "replayed_calls": getattr(elicitor, "replayed", None),
    }
    house_panel.write_result(summary, out_dir / "summary.json")
    (out_dir / "summary.md").write_text(
        render_markdown(summary), encoding="utf-8", newline="\n"
    )
    print(f"{house_panel.LABEL}: wrote {out_dir / 'summary.json'} and summary.md")
    if hasattr(elicitor, "close"):
        elicitor.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
