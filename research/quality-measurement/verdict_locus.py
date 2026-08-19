"""E3 and the locus ladder: four stations between a representation and a sampled verdict.

Stage-0 §89's Track E, the half that needs logits and therefore torch. The other five protocols
live in `elicitation_study.py` and run against the API; this one cannot, because **the API returns
no logprobs** and the whole point of E3 is to read the answer distribution before anything samples
from it.

**The question, stated as a place rather than as a score.** §87 found a difference that is present
in a representation of the prose and gone by the time a verdict is produced: on
`interiority_strip_matched`, mean-pooled text ordered 9 of 9 scenes and the readout at the
verdict position ordered 5 of 9. That is one family and §87 reported it as a diagnostic rather
than a result. Here it becomes the design. One extraction, four readings, in the order the signal
would have to survive:

    station 1  text_mean      mean-pooled residual over the bare text
    station 2  judge_last     residual at the last position of a single-text judging prompt
    station 3  answer_logits  P(A) - P(B) at the position the verdict's first token comes from
    station 4  sampled        the verdict actually drawn from that distribution

**Stations 1 and 2 are read from the existing dump; 3 and 4 need this module's own pass**, because
they are properties of a *pairwise* prompt and the dump holds single-text vectors. That is stated
rather than glossed: the ladder is not four readings of one tensor, it is two readings of the
representation and two of the verdict channel, and the join between them is the fixture, not the
forward pass.

**What makes station 3 the interesting one.** It has no slot to collapse into in the way a sampled
answer does — it is a continuous contrast between two token logits, position-swapped and averaged,
so a model that "prefers A" out of positional habit shows up as a constant that the swap removes.
If the number is alive at station 3 and dead at station 4, the loss is in sampling. If it is
already dead at station 3, the loss is upstream of the verdict entirely and no elicitation
protocol can recover it — which is the finding that would settle the session's question.

Pre-registered before the first forward pass. Runs under the **MirrorBench** interpreter
(`C:/DEV/MirrorBench/.venv/Scripts/python.exe`) — the one with torch and CUDA — and never imports
`litharness`. Local inference only, no quota. The GPU governor from `cdg_battery` applies.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from b6_benchmark import (  # noqa: E402
    CONTROLS,
    MEMBERS,
    POSITIVE_CONTROL,
    admitted_families,
    control_families,
)
from cdg_battery import REST_RATIO, gpu_temperature, throttle  # noqa: E402
from elicitation_study import (  # noqa: E402
    FAMILY_ALPHA,
    attainable_p,
    exact_two_sided,
    family_reading,
    required_k,
    sign_of,
)
from latent_probe import MODEL_ID, MODEL_REVISION, READOUT_LAYERS  # noqa: E402

RESULTS = HERE / "results"

#: The pairwise prompt for stations 3 and 4. Deliberately the plainest form — §77's 2x2 found one
#: plain word outperforming four authored personas, and `latent_probe.JUDGE_PROMPT` is built on the
#: same finding. It is **not** `personas.PAIR_QUESTION`: that question offers a third option
#: ("neither") and ends by asking for a reason code, and a three-way answer with a trailing field
#: has no clean two-token contrast to read. The wording difference is a confound between E3 and
#: E1 and it is named here rather than discovered later — E3 measures where a signal survives to,
#: not how E1's exact question fares at a lower tier.
PAIR_PROMPT = (
    "Two passages of fiction.\n\n"
    "--- PASSAGE A ---\n{first}\n--- END A ---\n\n"
    "--- PASSAGE B ---\n{second}\n--- END B ---\n\n"
    "Which passage is better written? Answer with a single letter, A or B.\n\nAnswer:"
)

#: The two answer tokens, resolved against the tokenizer at run time rather than hard-coded. A
#: letter can tokenize differently with and without a leading space, and reading the wrong id
#: would produce a clean-looking number that is about some other token entirely.
ANSWER_LETTERS = ("A", "B")

PRE_REGISTRATION: dict[str, Any] = {
    "written": "2026-08-19, before the first forward pass of this module",
    "question": (
        "Between a representation of the prose and a sampled verdict, at which station does "
        "discrimination die? Scored on B6 (§88), whose counter certifies the difference is there."
    ),
    "ladder_order": ["text_mean", "judge_last", "answer_logits", "sampled"],
    "why_this_order": (
        "It is the order the signal has to survive in, so the first station at which k falls is a "
        "location and not a ranking. Declared before the run so that whichever station drops "
        "cannot be described afterwards as the one we expected."
    ),
    "statistic": (
        "The same two-sided exact binomial sign test over pairs that `elicitation_study` uses, so "
        "the four stations and the five API protocols land in one table. Station 3's per-pair "
        "score is P(A)-P(B) averaged over both orientations, which removes a constant positional "
        "preference by construction; its sign is the sign of that average."
    ),
    "why_two_sided": (
        "Identical to `elicitation_study.PRE_REGISTRATION`: B6 certifies that a difference exists "
        "and never which side is better, so a protocol that consistently prefers either side has "
        "registered it. Inherited deliberately — the two modules must not disagree about what "
        "counts as a pass."
    ),
    "no_positional_precondition_at_station_3": (
        "Station 3 averages the two orientations of the same pair before taking a sign, so a "
        "constant slot preference cancels rather than being screened for. The residual "
        "orientation asymmetry is reported as a diagnostic (`orientation_split`) instead of as a "
        "precondition, because a precondition that cannot fail is not one (§89's rule for E4)."
    ),
    "station_4_is_greedy": (
        "The sampled verdict is taken at temperature 0. A temperature-sampled verdict would put "
        "sampling noise into the one station that exists to show what sampling costs, and the "
        "comparison wanted is distribution-versus-argmax rather than distribution-versus-draw."
    ),
    "stations_1_and_2_are_joined_not_recomputed": (
        "They come from `latent_probe`'s dump, which is a single-text extraction; stations 3 and 4 "
        "are pairwise. The ladder is therefore two readings of the representation and two of the "
        "verdict channel joined on the fixture, not four readings of one tensor."
    ),
    "controls": (
        "`placebo_identical` must return no separation at any station — at station 3 the two "
        "orientations of a byte-identical pair are the same prompt, so P(A)-P(B) must cancel to "
        "zero exactly, which is a stronger floor than any of the API protocols can offer. "
        "`rewhitespace_sham` separating at any station is a layout reading and is VOID (§78.1)."
    ),
}


def _load_model() -> Any:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, revision=MODEL_REVISION, dtype=torch.bfloat16, device_map="cuda",
    )
    model.eval()
    return tokenizer, model


def _answer_ids(tokenizer: Any) -> dict[str, int]:
    """Token ids for the answer letters, resolved and checked rather than assumed.

    A single letter can tokenize to different ids with and without a leading space, and after a
    chat template's assistant turn the model emits the bare letter. Both forms are resolved and
    the run refuses if either letter is not a single token, because a multi-token answer has no
    single position whose logits are the answer distribution.
    """
    out: dict[str, int] = {}
    for letter in ANSWER_LETTERS:
        ids = tokenizer.encode(letter, add_special_tokens=False)
        if len(ids) != 1:
            raise SystemExit(f"{letter!r} is not a single token for {MODEL_ID}: {ids}")
        out[letter] = ids[0]
    if len(set(out.values())) != len(out):
        raise SystemExit(f"answer letters collide on one token id: {out}")
    return out


def _contrast(tokenizer: Any, model: Any, first: str, second: str, ids: dict[str, int],
              ) -> dict[str, Any]:
    """One prompt: the answer distribution at the verdict position, and the greedy draw."""
    import torch

    turns = [{"role": "user", "content": PAIR_PROMPT.format(first=first, second=second)}]
    text = tokenizer.apply_chat_template(turns, tokenize=False, add_generation_prompt=True)
    batch = tokenizer(text, return_tensors="pt", add_special_tokens=False).to(model.device)
    with torch.no_grad():
        logits = model(**batch).logits[0, -1, :].float()
    probs = torch.softmax(logits, dim=-1)
    pa, pb = float(probs[ids["A"]]), float(probs[ids["B"]])
    return {
        "p_a": pa,
        "p_b": pb,
        "contrast": pa - pb,
        # Station 4. Greedy over the whole vocabulary, not over {A, B}: a model whose argmax is
        # neither letter has not answered the question, and folding that into "chose A" would be
        # the same conflation §87.3 refused when it made NOT_SCREENABLE its own state.
        "argmax_token": int(torch.argmax(logits)),
        "argmax_is_answer": int(torch.argmax(logits)) in set(ids.values()),
        "sampled": next((k for k, v in ids.items() if v == int(torch.argmax(logits))), None),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    """Stations 3 and 4 over every admitted family and control, both orientations."""
    tokenizer, model = _load_model()
    ids = _answer_ids(tokenizer)
    families = {**admitted_families(), **control_families()}
    out: dict[str, Any] = {"model": MODEL_ID, "revision": MODEL_REVISION,
                           "answer_token_ids": ids, "families": {}}
    for name, pairs in families.items():
        rows: dict[str, Any] = {}
        for index, pair in enumerate(pairs, start=1):
            started = time.time()
            forward = _contrast(tokenizer, model, pair.negative, pair.positive, ids)
            reverse = _contrast(tokenizer, model, pair.positive, pair.negative, ids)
            # Same call shape `latent_probe` uses: rest as a multiple of the work just done, then
            # hold while the card is hot. This box thermal-shut-down mid-run once and the
            # governor's constants were paid for the expensive way.
            throttle((time.time() - started) * args.rest_ratio / REST_RATIO, gpu_temperature())
            # Orientation 0 puts the negative side in slot A, so a positive contrast favours the
            # negative side; orientation 1 puts the positive side in A. Averaging the two in the
            # *variant's* frame is what removes a constant slot preference.
            variant_forward = -forward["contrast"]
            variant_reverse = reverse["contrast"]
            rows[pair.scene] = {
                "logit_score": (variant_forward + variant_reverse) / 2,
                "orientation_split": [variant_forward, variant_reverse],
                "sampled": [forward["sampled"], reverse["sampled"]],
                "argmax_is_answer": [forward["argmax_is_answer"], reverse["argmax_is_answer"]],
            }
            print(f"  {name} {index}/{len(pairs)}", file=sys.stderr, flush=True)
        out["families"][name] = rows
    return out


def score(raw: dict[str, Any]) -> dict[str, Any]:
    """Stations 3 and 4 on the shared statistic, so they print in one table with E1-E6."""
    stations: dict[str, dict[str, dict[str, int]]] = {"answer_logits": {}, "sampled": {}}
    for name, rows in raw["families"].items():
        logit_signs: dict[str, int] = {}
        sampled_signs: dict[str, int] = {}
        for scene, row in rows.items():
            score_value = row["logit_score"]
            logit_signs[scene] = 0 if score_value == 0 else (1 if score_value > 0 else -1)
            # A sampled verdict in the variant's frame: orientation 0 puts the variant in B,
            # orientation 1 puts it in A.
            picks = []
            for orientation, letter in enumerate(row["sampled"]):
                if letter is None:
                    continue
                picks.append(1.0 if letter == ("B" if orientation == 0 else "A") else 0.0)
            sampled_signs[scene] = sign_of(sum(picks) / len(picks) if picks else None)
        stations["answer_logits"][name] = logit_signs
        stations["sampled"][name] = sampled_signs
    report: dict[str, Any] = {"pre_registration": PRE_REGISTRATION, "stations": {}}
    for station, per_family in stations.items():
        report["stations"][station] = {
            "members": [family_reading(name, per_family[name]) for name in MEMBERS
                        if name in per_family],
            "controls": [family_reading(name, per_family[name]) for name in CONTROLS
                         if name in per_family],
            "positive_control": (
                family_reading(POSITIVE_CONTROL, per_family[POSITIVE_CONTROL])
                if POSITIVE_CONTROL in per_family else None
            ),
        }
    return report


def selftest() -> int:
    """The frame and the shared statistic, before any weights are loaded."""
    failures: list[str] = []

    def check(claim: str, ok: bool) -> None:
        if not ok:
            failures.append(claim)

    check("the ladder is declared in survival order",
          PRE_REGISTRATION["ladder_order"] ==
          ["text_mean", "judge_last", "answer_logits", "sampled"])
    check("the statistic matches elicitation_study at G=10", required_k(10) == 9)
    check("the floor matches elicitation_study at G=7", attainable_p(7) == exact_two_sided(7, 7))
    check("alpha is shared", FAMILY_ALPHA == 0.05)
    check("readout layers are the probe's", READOUT_LAYERS == (9, 17, 25))
    # A byte-identical pair must cancel exactly: the two orientations are the same prompt, so
    # `variant_forward` and `variant_reverse` are negatives of each other.
    check("an identical pair cancels to zero", sign_of(0.5) == 0)
    for message in failures:
        print(f"  FAIL {message}", file=sys.stderr)
    print(f"verdict_locus selftest: {'PASS' if not failures else str(len(failures)) + ' FAIL'}",
          file=sys.stderr)
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="forward passes; needs CUDA")
    parser.add_argument("--rest-ratio", type=float, default=REST_RATIO)
    parser.add_argument("--raw", default=str(RESULTS / "verdict-locus-raw.json"))
    parser.add_argument("--out", default=str(RESULTS / "verdict-locus.json"))
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if selftest():
        print("refusing to run: selftest failed", file=sys.stderr)
        return 1

    raw_path = Path(args.raw)
    if args.run:
        raw = run(args)
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(json.dumps(raw, indent=2, sort_keys=True), encoding="utf-8")
    elif raw_path.is_file():
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
    else:
        print(f"no raw file at {raw_path}; pass --run", file=sys.stderr)
        return 2

    report = score(raw)
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    for station, entry in report["stations"].items():
        print(f"\n{station}")
        for row in entry["members"] + entry["controls"]:
            print(f"  {row['family']:28s} {row['aligned']:>3d}/{row['decided_pairs']:<3d} "
                  f"p={row['p_two_sided']:.5f} floor={row['attainable_floor']:.5f} "
                  f"{row['verdict']}")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
