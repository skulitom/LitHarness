"""Does this box reproduce a forward pass and a sampled continuation bit-exactly?

**Run before any force, because the answer decides a control's tolerance and a tolerance chosen
after a control fails is the bar-moving §89's rulebook is about.**

`placebo_identical` is not a null in this programme, it is an *arithmetic check* (§89.4): the two
sides are byte-identical text, so the effect must be `0.000000`, and the machinery that makes
that true is `force_harness.text_seed` — every stochastic step seeded from the digest of the text
it acts on. But seeding is a statement about the *software*. Whether bf16 matmul reduction order
on this particular card reproduces across calls is a statement about the *hardware*, and this
repository has been wrong before about things it assumed rather than measured.

So the tolerance is measured here and printed, and §1.7 of the programme takes whichever branch
this probe returns:

    EXACT        replay is bit-exact; the placebo tolerance is 0.0 and the control is an
                 arithmetic check, as designed
    NOISY        replay is not bit-exact; the measured noise scale is printed, the placebo
                 becomes an equivalence test against it, and the weakening is recorded as a
                 property of this box rather than of the design

Four checks, and the fourth is the one that matters most because it is the actual placebo path:

1. same text, same call, twice — forward-pass determinism within a process
2. same text, same seed, two sampled continuations — sampling determinism
3. a text against a byte-identical *copy* built separately — that identity of value, not of
   object, is what the placebo relies on
4. the same text scored inside two different surrounding *batches* is **not** checked, and that
   is deliberate: `force_gpu.sample_continuations` batches exactly the K replicates of one
   prompt and nothing else, so batch composition is a pure function of the text and never
   varies. Check 2 runs on that batched path, which is the path the programme uses; a probe that
   certified a looped path the programme abandoned would certify nothing.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import force_gpu  # noqa: E402
from force_harness import RESULTS, digest, load_pairs  # noqa: E402

#: Below this the two runs are the same number in every digit anyone will read.
EXACT_EPS = 0.0

PRE_REGISTRATION = {
    "question": "is replay bit-exact on this box, for the two operations every force uses",
    "branch_exact": "placebo tolerance 0.0; the control is an arithmetic check (§89.4)",
    "branch_noisy": "placebo becomes an equivalence test against the MEASURED noise scale, "
                    "and the weakening is a recorded property of the box",
    "declared_before": "any force ran",
    "not_measured": "batched-generation determinism — the programme generates replicates one "
                    "at a time so batch composition never enters",
}


def probe(family: str, head: str, text: str, *, tokens: int) -> dict[str, Any]:
    governor = force_gpu.Governor()
    prefix, target = text[: len(text) // 2], text[len(text) // 2 :]

    first, _ = force_gpu.token_logprobs(family, prefix, target, head=head, governor=governor)
    second, _ = force_gpu.token_logprobs(family, prefix, target, head=head, governor=governor)
    # Identity of value rather than of object: the placebo builds its second side as a separate
    # string with the same content, and that is the path being certified here.
    copied_prefix = "".join(list(prefix))
    third, _ = force_gpu.token_logprobs(family, copied_prefix, target, head=head, governor=governor)

    deltas = [abs(a - b) for a, b in zip(first, second, strict=True)]
    copy_deltas = [abs(a - b) for a, b in zip(first, third, strict=True)]

    samples_a = force_gpu.sample_continuations(
        family, text, k=2, max_new_tokens=tokens, head=head, governor=governor
    )
    samples_b = force_gpu.sample_continuations(
        family, "".join(list(text)), k=2, max_new_tokens=tokens, head=head, governor=governor
    )
    identical = [a == b for a, b in zip(samples_a, samples_b, strict=True)]

    forward_max = max(deltas + copy_deltas) if deltas else 0.0
    exact = forward_max <= EXACT_EPS and all(identical)
    return {
        "family": force_gpu.family_provenance(family, head),
        "scored_tokens": len(first),
        "forward_repeat_max_abs_delta": forward_max,
        "forward_repeat_mean_abs_delta": round(statistics.fmean(deltas), 12) if deltas else 0.0,
        "copy_vs_original_max_abs_delta": max(copy_deltas) if copy_deltas else 0.0,
        "sampled_continuations_identical": identical,
        "sample_digests": [digest(s) for s in samples_a + samples_b],
        "verdict": "EXACT" if exact else "NOISY",
        "governor": governor.report(),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    pairs = load_pairs(("aligned",))
    text = pairs[0].high
    rows = [probe(family, "base", text, tokens=args.tokens) for family in args.families]
    verdicts = {row["family"]["family"]: row["verdict"] for row in rows}
    overall = "EXACT" if all(v == "EXACT" for v in verdicts.values()) else "NOISY"
    tolerance = 0.0 if overall == "EXACT" else max(
        row["forward_repeat_max_abs_delta"] for row in rows
    )
    return {
        "pre_registration": PRE_REGISTRATION,
        "probe_text_digest": digest(text),
        "per_family": rows,
        "verdict": overall,
        "placebo_tolerance": tolerance,
        "reading": (
            "replay is bit-exact on both families; placebo_identical keeps its arithmetic-check "
            "role and its tolerance is 0.0"
            if overall == "EXACT"
            else "replay is not bit-exact; placebo_identical is downgraded to an equivalence "
                 f"test against a measured noise scale of {tolerance:.3e}, which is a property "
                 "of this box and is recorded as one"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--families", nargs="+", default=["gemma-3-4b", "qwen2.5-3b"])
    parser.add_argument("--tokens", type=int, default=64)
    parser.add_argument("--out", default=str(RESULTS / "force-determinism.json"))
    args = parser.parse_args(argv)

    report = run(args)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "per_family"}, indent=2))
    for row in report["per_family"]:
        print(
            f"{row['family']['family']:<14} {row['verdict']:<6} "
            f"forward max delta {row['forward_repeat_max_abs_delta']:.3e}  "
            f"samples identical {row['sampled_continuations_identical']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
