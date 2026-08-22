"""Track F4: the surprisal field — surprising forward, inevitable backward.

Stage-0 §99. Token-level surprisal, `-log p(token | prefix)`, from pinned **base** checkpoints:
"surprise while reading" in the information-theoretic sense, and a base head by construction
because surprisal is precisely the quantity RLHF warps.

**The non-claim comes first, because it disqualifies arms rather than caveating them.** Quality is
**not monotone in surprisal at any level**. Maximal surprise is noise, minimal is cliché, and the
published perplexity-as-quality record is weak for exactly that reason. Every statistic here is a
**shape** statistic. An arm whose reading reduces to *"higher (or lower) mean surprisal is
better"* is mis-specified and VOID by §99's opening paragraph, not by a later measurement.

**F4 is the only instrument in this repository with an external validation target.** Human reading
times are approximately linear in surprisal (Levy 2008; Smith & Levy 2013). That calibration is
evidence about the instrument and never about a book.

**The formatting control, and why there are two of them.** §99.1 in code: under the directive's
default — compute everything on canonicalized text — the whitespace sham compares
`canonical(x)` against `canonical(rewhitespace(x))`, and a canonicalizer that is total over
whitespace makes those **byte-identical before a model sees either**. The effect is then exactly
zero for any model including a broken one, which is a control that cannot fail (§50). So:

* :func:`canonicalization_coverage` keeps the whitespace transform and reports it as what it
  actually is — a unit test asserting our own canonicalizer is total. Non-zero means choice (i)
  is not in force.
* :func:`paragraph_break_sham` is the real §78.1 control. A canonicalizer may normalize the
  paragraph *separator*; it must not move where paragraphs *break*, or it is rewriting rather
  than normalizing. Relocating a boundary leaves every word and the whole vocabulary untouched
  and still changes the token stream, so it can move surprisal, so it can fail.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import force_gpu  # noqa: E402

# `rewhitespace` is defined and fully typed in `ablate.py`; `force_harness` re-exports it only
# implicitly, and --strict's no-implicit-reexport forbids reading an implicit re-export.
from ablate import rewhitespace  # noqa: E402
from force_harness import (  # noqa: E402
    RESULTS,
    digest,
    provenance,
)

DERIVED = HERE / "derived"

#: Grains the trajectory statistics are reported at. Declared here rather than chosen per run.
GRAINS = ("sentence", "paragraph")

#: Verbatim-token run at or above which a text is treated as memorized and quarantined from every
#: NLL reading. Pre-registered before the probe is pointed at anything (§99.3, head-type addendum
#: §2). Thirty-two greedy tokens reproducing the source exactly is far past coincidence for prose
#: and comfortably short of requiring a full passage.
MEMORIZATION_RUN_TOKENS = 32

PRE_REGISTRATION: dict[str, Any] = {
    "track": "F4 surprisal field",
    "ledger": "plan/stage-0-decisions.md §99",
    "head": "base only, by construction — surprisal is the quantity RLHF warps",
    "non_claim": "quality is NOT monotone in surprisal at any level. Maximal surprise is noise, "
                 "minimal is cliche. Every statistic is a SHAPE statistic, and an arm whose "
                 "reading reduces to 'higher (or lower) mean surprisal is better' is "
                 "mis-specified and VOID by §99 rather than by a measurement.",
    "external_anchor": "human reading times are approximately linear in surprisal (Levy 2008; "
                       "Smith & Levy 2013); N400 tracks it. Calibration is evidence about the "
                       "INSTRUMENT and never about a book.",
    "canonicalization": "choice (i): every statistic is computed on canonical text. The function "
                        "is committed and digested into every cache key.",
    "controls": {
        "placebo_identical": "exactly zero on every statistic; arithmetic check",
        "canonicalization_coverage": "the whitespace transform, reported as a unit test of our "
                                     "own canonicalizer rather than as a formatting control. "
                                     "Under choice (i) it is zero BY CONSTRUCTION if the "
                                     "canonicalizer is total, so it cannot fail on the model and "
                                     "is not §78.1's control (§50).",
        "paragraph_break_sham": "the real §78.1 control: same words, same canonical whitespace, "
                                "relocated paragraph boundary. It can move surprisal and so it "
                                "can fail; an interval excluding 0.50 VOIDs the arm.",
    },
    "memorization_gate": {
        "verbatim_run_tokens": MEMORIZATION_RUN_TOKENS,
        "rule": "any pretraining-era text failing the probe is quarantined from all NLL "
                "readings. Mother of Learning and all RoyalRoad text are presumed contaminated "
                "until probed.",
    },
    "substrate_order": [
        "the twenty fitness books — contamination-proof by construction",
        "own-generated pool as it grows",
        "RoyalRoad and anchors, per text, only after each clears the probe",
    ],
    "declared_before": "any surprisal series was computed",
}


# --------------------------------------------------------------------------- canonicalization


#: Whitespace preceded by sentence-final punctuation. **Fixed-width lookbehind on purpose**: an
#: optional closing quote inside the lookbehind is variable-width and Python rejects it outright,
#: and consuming the quote instead would delete a character from the text — which would break
#: `paragraph_break_sham`'s guarantee that it changes no words. The cost is that a sentence ending
#: `he said."` does not split here. Conservative in the direction that cannot corrupt prose.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def canonical(text: str) -> str:
    """The one text-normalising function every F4 statistic runs behind. Committed, and digested.

    **Total over whitespace and conservative about everything else.** It collapses runs of spaces
    and tabs, normalises the paragraph separator to exactly one blank line, strips trailing
    whitespace per line, and touches not one character of any word — no case folding, no
    punctuation substitution, no quote or dash normalisation. Anything beyond whitespace would be
    editing the prose rather than normalising its layout, and F4's whole claim is that it reads
    prose.

    **It deliberately preserves where paragraphs break.** That is what makes
    :func:`paragraph_break_sham` a control that can fail: the separator is normalised, the
    structure is not, so relocating a boundary survives canonicalization and reaches the model.
    """
    flattened = text.replace("\r\n", "\n").split("\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in flattened]
    # Rebuild paragraphs from runs of non-empty lines, then join with exactly one blank line.
    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines:
        if line:
            current.append(line)
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs)


def is_canonical(text: str) -> bool:
    """Idempotence, which is the property that makes choice (i) meaningful."""
    return canonical(text) == text


def paragraphs_of(text: str) -> list[str]:
    return [p for p in canonical(text).split("\n\n") if p]


def sentences_of(text: str) -> list[str]:
    out: list[str] = []
    for paragraph in paragraphs_of(text):
        out.extend(s for s in _SENTENCE_END.split(paragraph) if s.strip())
    return out


# ------------------------------------------------------------------------------- the controls


def canonicalization_coverage(text: str) -> dict[str, Any]:
    """Does the canonicalizer absorb the whitespace transform? A unit test, labelled as one.

    **This is not §78.1's formatting control and must never be reported as one.** Under choice (i)
    a total canonicalizer makes `canonical(rewhitespace(x))` byte-identical to `canonical(x)`, so
    the reading is zero for any model, including one that reads nothing but layout. What it can
    tell us is whether choice (i) is actually in force: a non-zero reading means the canonicalizer
    leaked, and every F4 number computed behind it is then a number about formatting.
    """
    base = canonical(text)
    shammed = canonical(rewhitespace(text, 1.0))
    identical = base == shammed
    return {
        "control": "canonicalization_coverage",
        "kind": "unit test of our own canonicalizer, not a model control",
        "identical_after_canonicalization": identical,
        "status": "PASS" if identical else "VOID",
        "why": "" if identical else (
            "the canonicalizer did not absorb the whitespace transform, so choice (i) is not in "
            "force and every F4 statistic behind it is partly about layout"
        ),
        "cannot_fail_on_the_model": True,
    }


def paragraph_break_sham(text: str, *, seed: str = "f4") -> str | None:
    """Same words, same canonical whitespace, one paragraph boundary moved. F4's real control.

    Returns `None` when the text cannot carry the transform — fewer than two paragraphs, or a
    paragraph too short to split. A pair whose transform changed nothing is a placebo wearing a
    control's name and is skipped rather than counted, which is `sham_pairs`' rule (§95.15's B25)
    applied to a different transform.
    """
    paragraphs = paragraphs_of(text)
    if len(paragraphs) < 2:
        return None
    # Deterministic choice: the longest paragraph, split at its middle sentence boundary. No RNG,
    # so the control's own re-runs are comparable — `surprisal`'s reasoning for fixed offsets.
    index = max(range(len(paragraphs)), key=lambda i: len(paragraphs[i]))
    parts = [s for s in _SENTENCE_END.split(paragraphs[index]) if s.strip()]
    if len(parts) < 2:
        return None
    cut = len(parts) // 2
    rebuilt = list(paragraphs)
    rebuilt[index : index + 1] = [" ".join(parts[:cut]), " ".join(parts[cut:])]
    out = "\n\n".join(rebuilt)
    return None if out == canonical(text) else out


# ------------------------------------------------------------------------------ the statistics


def surprisal_series(
    family: str,
    text: str,
    *,
    governor: force_gpu.Governor | None = None,
    head: str = "base",
) -> list[float]:
    """Per-token surprisal over canonical text. The series every F4 statistic is a shape of.

    Scored as a continuation of a single leading token so that every position after the first has
    a prefix, which is what `-log p(token | prefix)` requires. The first token has no prefix and
    is not scored: including it would make the series' opening a statement about the tokenizer's
    BOS handling rather than about prose.
    """
    body = canonical(text)
    if not body.strip():
        return []
    logprobs, _ids = force_gpu.token_logprobs(
        family, body[:1], body[1:], head=head, governor=governor
    )
    return [-lp for lp in logprobs]


def trajectory_shape(series: Sequence[float]) -> dict[str, Any]:
    """F4b: variance, burstiness and autocorrelation of the surprisal series.

    **Every one of these moves with the dialogue/exposition mix**, which is declared as a
    covariate in §99.2 rather than discovered afterwards. Dialogue is short-lined, high-variance
    and low-surprisal per token; exposition is the reverse. A shape difference between two texts
    with different mixes is a statement about the mix until the mix is controlled.

    Burstiness is the Fano-style coefficient of variation, `(sd - mean) / (sd + mean)`, which is
    bounded in [-1, 1] and is scale-free — deliberately, because a burstiness that scaled with the
    mean would smuggle the monotone claim §99 voids back in through the shape statistic.
    """
    values = [v for v in series if math.isfinite(v)]
    if len(values) < 8:
        return {"status": "INSUFFICIENT_N", "tokens": len(values)}
    mean = statistics.fmean(values)
    sd = statistics.pstdev(values)
    lag1 = _autocorrelation(values, 1)
    return {
        "status": "READ",
        "tokens": len(values),
        "mean_surprisal_NOT_A_QUALITY_READING": round(mean, 5),
        "sd": round(sd, 5),
        "burstiness": round((sd - mean) / (sd + mean), 5) if (sd + mean) else None,
        "autocorrelation_lag1": None if lag1 is None else round(lag1, 5),
    }


def _autocorrelation(values: Sequence[float], lag: int) -> float | None:
    if len(values) <= lag + 1:
        return None
    mean = statistics.fmean(values)
    denominator = sum((v - mean) ** 2 for v in values)
    if denominator == 0:
        return None
    numerator = sum(
        (values[i] - mean) * (values[i + lag] - mean) for i in range(len(values) - lag)
    )
    return numerator / denominator


def dialogue_share(text: str) -> float:
    """The declared F4b confound, measured rather than assumed: share of lines opening a quote."""
    lines = [line for line in canonical(text).split("\n") if line.strip()]
    if not lines:
        return 0.0
    # Escapes rather than the marks themselves: ruff flags ambiguous unicode in source,
    # and a curly quote that looks like a straight one is exactly the kind of thing that
    # should not sit unremarked in a file about reading text carefully.
    openers = {'"', "'", chr(0x201C), chr(0x2018)}
    quoted = sum(1 for line in lines if line.lstrip()[:1] in openers)
    return round(quoted / len(lines), 4)


def selftest() -> int:
    failures: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            failures.append(message)

    messy = "One   line.\r\n  Two line.\n\n\n\nA new  paragraph here.\nSame paragraph.  \n"
    once = canonical(messy)
    check(is_canonical(once), "canonical is not idempotent")
    check("\r" not in once and "\t" not in once, "canonical left carriage returns or tabs")
    check("\n\n\n" not in once, "canonical left a triple newline")
    check(sorted(once.split()) == sorted(messy.split()), "canonical changed the words")

    # The coverage check passes on a total canonicalizer, and says out loud that it cannot fail.
    coverage = canonicalization_coverage(messy)
    check(coverage["status"] == "PASS", f"coverage should pass: {coverage}")
    check(coverage["cannot_fail_on_the_model"], "coverage must declare that it cannot fail")

    # The real control changes the token stream while preserving every word.
    prose = (
        "The archive was cold. Nobody had signed the register. She waited an hour.\n\n"
        "Outside the rain began. The road would be impassable by dark. He did not come."
    )
    moved = paragraph_break_sham(prose)
    check(moved is not None, "paragraph sham returned nothing on two full paragraphs")
    if moved is not None:
        check(moved != canonical(prose), "paragraph sham was a no-op")
        check(sorted(moved.split()) == sorted(canonical(prose).split()),
              "paragraph sham changed the words")
        check(canonical(moved) == moved, "paragraph sham left non-canonical text")
        # **The property that makes it a control**: it survives canonicalization, where the
        # whitespace transform does not.
        check(canonical(rewhitespace(prose, 1.0)) == canonical(prose),
              "whitespace transform survived canonicalization; choice (i) is not in force")

    check(paragraph_break_sham("One paragraph only. Two sentences.") is None,
          "a single-paragraph text cannot carry the sham and must return None")

    shape = trajectory_shape([1.0, 5.0, 2.0, 8.0, 1.5, 6.0, 2.5, 7.0, 3.0])
    check(shape["status"] == "READ", f"shape should read: {shape}")
    check(-1.0 <= shape["burstiness"] <= 1.0, "burstiness must be bounded in [-1, 1]")
    check(trajectory_shape([1.0, 2.0])["status"] == "INSUFFICIENT_N", "short series must refuse")

    check(dialogue_share('"Hello," she said.\n\nHe left.') == 0.5, "dialogue share miscounted")

    check(len(sentences_of(prose)) == 6, f"sentence split: {sentences_of(prose)}")
    check(len(paragraphs_of(prose)) == 2, "paragraph split")

    for message in failures:
        print(f"FAIL {message}")
    print(f"surprisal_field selftest: {len(failures)} failures")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--out", default=str(RESULTS / "force-f4-g0.json"))
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    report = provenance(
        track="F4",
        pre_registration_track=PRE_REGISTRATION,
        canonicalization_digest=digest(canonical.__doc__ or ""),
        status="NOT_RUN",
        reading="G0 has not been run from this entry point yet; see writer of record",
    )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
