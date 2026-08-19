"""Does the instrument perceive more than it reports? A probe on internals against the verdict.

Track P of the latent-taste directive (2026-08-19). The panel collapses into positional bias on
near-twin pairs (§83's 0.73-0.83, §85's 0.6949) and is BLIND to `stat_flatten` outright (§81).
The hypothesis this module tests is that much of that is a **report** failure rather than a
**perception** failure: that features separating near-twins exist in a language model's internal
state and fail to reach a verbal verdict. If so the ceiling is adapter-shaped rather than
pretraining-shaped, and the fix is a different question from "wait for better models".

**What this module can and cannot say, stated before any number exists.**

A probe measures **discrimination**, never preference. Nothing here reads as "better prose", and
no result in this file upgrades any licence — §82 governs verbatim. The strongest sentence Track
P may ever produce is *the difference between these two texts is linearly decodable from a 4B
model's residual stream at a place where the panel could only answer a slot*. That is a claim
about an information channel, and it is worth making because at similarity 0.98 the panel cannot
currently say the texts differ **at all**.

**And one substitution is named rather than buried.** The panel is `claude-haiku-4-5`; the probe
reads `google/gemma-3-4b-it`, because open weights are the only internals available. So this is
not a probe of the panel's own state, and no result here says what Haiku perceives. It says what
a small open model's representation carries — a lower bound on decodability from text of this
kind, from a model far below the panel's tier. A positive result therefore bounds the report
channel from below; a negative one is evidence about 4B and, per the kill condition, closes the
track rather than condemning the hypothesis.

**Two readouts, because they ask different questions.**

* `text_mean` — mean-pooled residual over the tokens of the bare text. The directive's
  pre-registered readout. Asks: *is the difference present in a representation of the prose?*
* `judge_last` — residual at the final prompt position of a single-text judging prompt, the
  position the first token of a verdict is generated from. Asks: *is the difference present in
  the state a verdict is produced from?* This is the readout that actually speaks to
  report-versus-perception, and it is declared **secondary** because the directive named the
  first. It may not carry a B6 proposal on its own.

**The multiplicity problem, and why there is no Bonferroni over layers.** Three layer depths per
family would be three chances to clear a null. Rather than correct after the fact, the family
statistic *is* the maximum `k` over the three layers, and :func:`layer_max_null` builds the null
of that maximum by applying each of the `2**G` label flips to all three layers at once. The
correction is exact and costs no power that a per-layer test would have kept. Across families the
control is the directive's own replication rule, and both the uncorrected and the family-wise
bars are declared in :data:`PRE_REGISTRATION` so neither can be selected afterwards.

Runs under the **MirrorBench** interpreter (`C:/DEV/MirrorBench/.venv/Scripts/python.exe`) — it
is the one with torch and CUDA, and this module never imports `litharness`. See RUNBOOK.md for
the two-interpreter rule. `--score` needs no GPU and runs anywhere numpy does.

Cost: local inference only. ~200 forward passes of ~1,400 tokens on a 4B model, minutes, no quota.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from itertools import product
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from cdg_battery import (  # noqa: E402
    PAUSE_ABOVE_C,
    REST_RATIO,
    RESUME_BELOW_C,
    digest,
    gpu_temperature,
    throttle,
)
from latent_fixtures import (  # noqa: E402
    FLOOR_FAMILIES,
    P0_NAMES,
    P0_PLUS_NAMES,
    Pair,
    build_families,
    drop_degenerate,
    exact_flip_null,
    gram,
    p0_features,
    signs_from_gram,
    unscoreable,
)

RESULTS = HERE / "results"

#: The digest manifest's slot inside the dump. Prefixed so it can never collide with a vector
#: key, which are all `readout|layer|family|scene|sign`.
MANIFEST_KEY = "__manifest__"

#: Pinned by commit, not by branch: a probe number is a property of a specific set of weights.
MODEL_ID = "google/gemma-3-4b-it"
MODEL_REVISION = "093f9f388b31de276ce2de164bdc2081324b9767"
#: Verified on this machine, not recalled: 34 decoder layers, hidden size 2,560.
N_LAYERS = 34
D_MODEL = 2560
#: Roughly quarter, half and three-quarter depth. The final entry of `hidden_states` is excluded
#: deliberately — it has the model's final norm applied and sits two orders of magnitude below
#: its neighbours in norm, so pooling it beside the others would compare different unit systems.
READOUT_LAYERS = (9, 17, 25)

#: The single-text judging prompt for the `judge_last` readout. Deliberately the plainest form
#: §77's 2x2 found outperformed four authored personas, and deliberately *not* a rubric: a
#: criterion we wrote cannot be evidence about what a judge perceives (§79's rule, borrowed).
JUDGE_PROMPT = (
    "Read the passage below and judge its quality as fiction.\n\n"
    "--- PASSAGE ---\n{text}\n--- END PASSAGE ---\n\n"
    "Your verdict:"
)

PRE_REGISTRATION: dict[str, Any] = {
    "written": "2026-08-19, before the first forward pass",
    "governs": "stage-0 §82 verbatim: no result in this file upgrades any licence.",
    "statistic": (
        "k = the number of scenes whose held-out pair is ordered correctly under "
        "leave-one-scene-out, out of G. The estimator is the unit-normalised mean of the "
        "training scenes' paired difference vectors; it has no hyperparameter, which is the "
        "only reason a held-out sign test on it means what it appears to mean."
    ),
    "null": (
        "Exact and exhaustive: all 2**G within-pair label flips, each re-running the full "
        "leave-one-scene-out pipeline. p is the fraction of flips reaching the observed k or "
        "better, the observed assignment included. Smallest attainable p is 1/2**G — 0.0039 at "
        "G=8, 0.0010 at G=10. No sampling, no asymptotics, no bootstrap."
    ),
    "layer_multiplicity": (
        "The family statistic is max(k) over the three readout layers, and its null is built by "
        "applying each flip vector to all three layers at once. Exact, and no Bonferroni."
    ),
    "alpha_uncorrected": 0.05,
    "alpha_family_wise": 0.00625,
    "family_wise_rule": (
        "0.05 divided by the eight non-floor families. Attainable only at k=G for G=8 (p=0.0039) "
        "and at k=G for G=10 (p=0.0010); k=9 of 10 reads p=0.0107 and clears the uncorrected bar "
        "only. Both numbers are reported for every family so neither can be chosen afterwards — "
        "§81's lesson, which is that a rule registered as a point estimate cannot be tightened "
        "once the numbers are in."
    ),
    "beats_p0": (
        "An internal claim on a family requires probe max-k STRICTLY GREATER than both surface "
        "baselines' max-k on that same family, under the identical pipeline and null. P0 is "
        "`authorship_tells.features` over system-stripped prose — the space §83 and §85 measure "
        "register movement in. P0+ adds three digit and status-slot counts on unstripped text, "
        "because `strip_system` deletes the only line `stat_flatten` edits and a probe beating "
        "an omission of ours would not be beating surface measurement. If either baseline clears "
        "its own null on a family, that family is CLOSED to P: surface features already separate "
        "it and internals add nothing there."
    ),
    "replication": (
        "A Track-P positive requires TWO distinct non-floor families that each clear the "
        "uncorrected bar AND beat both baselines. One family clearing alone is recorded as "
        "unreplicated and proposes nothing."
    ),
    "floors": (
        "placebo_identical (byte-identical sides, §85), states_tea_vs_sober (§83's inert "
        "placebo) and rewhitespace_sham (§78.1's formatting sham) are scored FIRST. The floor "
        "band's floor is declared here rather than derived, because §85's zero-drift placebo "
        "made a zero-width band and the arm it was supposed to protect failed a rule that was "
        "really an artifact: ANY floor family clearing alpha_uncorrected=0.05 voids every "
        "non-floor family measured under the same readout, and the run reports VOID rather than "
        "a corrected number. placebo_identical additionally must return k=0 with "
        "unscoreable_pairs=G; anything else is a bug in this module, not a finding."
    ),
    "readouts": (
        "text_mean is primary (the directive's 'mean-pooled'). judge_last is secondary and may "
        "not carry the B6 proposal alone; it is reported in full regardless of outcome."
    ),
    "quadrant": {
        "probe_separates_panel_void": (
            "Report-channel deficit confirmed at 4B. Propose fixture family B6 "
            "(probe-panel divergence pairs) FOR OPERATOR ADMISSION ONLY."
        ),
        "probe_fails_panel_void": "Perception deficit at this scale. Record the negative; close.",
        "probe_separates_panel_separates": "Instruments agree; probe is a free cross-check.",
        "probe_fails_panel_separates": "Panel outran 4B internals; scale ladder to the operator.",
    },
    "kill": (
        "No non-floor family clears its null under scene-grouped CV on either readout => record "
        "'perception-limited at 4B', close Track P, and let the quadrant's second row stand."
    ),
    "not_measured": (
        "Preference. Quality. Anything about what claude-haiku-4-5 perceives — the probe reads "
        "gemma-3-4b-it because open weights are the only internals available, and that "
        "substitution is a limit of the result, not a detail of the method."
    ),
}


#: What the panel is recorded as doing on each family, transcribed from the ledger rather than
#: re-measured. These are the *other* half of a B6 pair: a fixture belongs in the proposal only
#: when a counter decides it and the panel does not. Every row cites the entry it came from so a
#: reader can check the transcription, and `read` is the ledger's own word for the outcome.
PANEL_VERDICTS: dict[str, dict[str, Any]] = {
    "stat_flatten": {"read": "BLIND", "rate": 0.5437, "note": "estimate on the wrong side of "
                     "indifference; interval spans 0.5", "where": "§81"},
    "interiority_strip_matched": {"read": "SPANS_NULL", "rate": 0.3889, "note": "DETECTS as "
                                  "registered, UNDECIDED strict; interval [0.1667, 0.6667]",
                                  "where": "§81"},
    "repair_emdash": {"read": "VOID", "rate": 0.2734, "note": "bias 0.6949 at Haiku and 0.6087 "
                      "at Sonnet — void at both tiers", "where": "§85, §85.1"},
    "exemplar_vs_sober": {"read": "READABLE_AT_SONNET", "rate": 0.6484, "note": "VOID at Haiku "
                          "(bias 0.766), clean at Sonnet (bias 0.490)", "where": "§85, §85.1"},
    "repair_interiority": {"read": "SEPARATES", "rate": 0.9509, "note": "1.0000 at Sonnet, bias "
                           "0.500", "where": "§85, §85.1"},
    "filler_inject": {"read": "SEPARATES", "rate": None, "note": "a detected DEGRADER",
                      "where": "§70"},
    "states_drunk_vs_sober": {"read": "VOID", "rate": None, "note": "bias 0.828", "where": "§83"},
    "states_trip_vs_sober": {"read": "VOID", "rate": None, "note": "bias 0.762", "where": "§83"},
}

#: The panel readings that mean "this instrument did not decide the pair". A B6 member needs one
#: of these *and* a counter nameable in advance that decides every decidable pair.
UNDECIDED_READS = ("BLIND", "VOID", "SPANS_NULL")

#: The counter each family's transform makes obvious **before anyone looks at a result** — the
#: quantity the edit is defined in terms of. A family with no entry here has no a-priori counter
#: and cannot join B6, whatever a scan turns up.
#:
#: **This exists because `best_k` is a maximum over twenty-eight features and cannot be read as
#: one counter's score.** The first draft of the rule admitted §83's state arms at 7 of 8 on that
#: basis; with twenty-eight features scanned, 7 of 8 somewhere is unremarkable, and those arms are
#: precisely the families §86 records as undecided by surface *and* internals. A benchmark member
#: has to be a difference somebody could have specified in advance, not the best of a sweep.
A_PRIORI_COUNTER: dict[str, str] = {
    "stat_flatten": "system_digit_count",
    "interiority_strip_matched": "interior_per_1k",
    "repair_interiority": "interior_per_1k",
    "repair_emdash": "em_per_1k",
    "filler_inject": "words",
}


def _counter_orders_all(pairs: list[Pair], counter: str) -> bool:
    """Does one named counter separate every decidable pair in a single direction?"""
    signs = set()
    for pair in pairs:
        after = p0_features(pair.positive, steelman=True)[counter]
        before = p0_features(pair.negative, steelman=True)[counter]
        if after != before:
            signs.add(after > before)
    return len(signs) == 1


def propose_b6(report: dict[str, Any]) -> dict[str, Any]:
    """The fixture family this run proposes, derived from the results rather than chosen.

    **Proposed, never admitted.** §84 puts what panel v2 is selected on in the operator's hands,
    and §82 forbids any machine result from moving a licence. This function emits a candidate and
    the rule that produced it; admitting it is somebody else's act.

    The directive's B6 was "probe-panel divergence pairs". The run says the cheaper family is
    strictly better: the probe never beat a counter, so the divergence worth benchmarking is
    **counter-decidable / panel-undecided**. It needs no GPU, no open weights and no model pin,
    it reproduces from committed fixtures in one command, and it tests the same channel.
    """
    families = build_families()
    members, rejected = [], []
    for name, entry in report["families"].items():
        if entry["is_floor"] or name not in PANEL_VERDICTS:
            continue
        panel = PANEL_VERDICTS[name]
        counter = A_PRIORI_COUNTER.get(name)
        row: dict[str, Any] = {"family": name, "groups": entry["groups"], "panel": panel,
                               "a_priori_counter": counter}
        if counter is None:
            row["why_not"] = (
                "no counter is nameable from the transform, so any separation would be the best "
                "of a sweep over twenty-eight features"
            )
            rejected.append(row)
            continue
        pairs, _ = drop_degenerate(name, families[name])
        deltas, ties = [], []
        for pair in pairs:
            after = p0_features(pair.positive, steelman=True)[counter]
            before = p0_features(pair.negative, steelman=True)[counter]
            (ties if after == before else deltas).append(pair.scene)
        signs = [
            1 for pair in pairs
            if p0_features(pair.positive, steelman=True)[counter]
            != p0_features(pair.negative, steelman=True)[counter]
        ]
        decidable = len(signs)
        # One direction, one counter, every decidable pair: no fitting and nothing to hold out,
        # which is the point — a benchmark member should be checkable by inspection.
        ordered = _counter_orders_all(pairs, counter)
        row |= {"decidable_pairs": decidable, "structural_ties": ties, "orders_all": ordered}
        if ordered and decidable >= entry["groups"] - 1 and panel["read"] in UNDECIDED_READS:
            members.append(row)
        else:
            row["why_not"] = (
                "the panel decides this family" if panel["read"] not in UNDECIDED_READS
                else "the a-priori counter does not order every decidable pair"
            )
            rejected.append(row)
    return {
        "status": "PROPOSED — NOT ADMITTED. Only the operator moves what panel v2 is selected on.",
        "name": "B6 counter-decidable / panel-undecided",
        "rule": (
            "A pair joins B6 when the counter its transform is DEFINED in terms of — named in "
            "A_PRIORI_COUNTER before any result is read — orders every decidable pair in one "
            "direction, structurally tied pairs are listed rather than counted, at least G-1 "
            "pairs are decidable, AND the ledger records the panel as BLIND, VOID or "
            "interval-spanning on the same fixture."
        ),
        "what_it_tests": (
            "The verdict channel, not perception: every member is a difference that is provably "
            "present in the text and provably absent from the panel's answer."
        ),
        "what_it_cannot_test": (
            "Preference. A counter orders a pair; it does not prefer one side. B6 grades whether "
            "a judge REGISTERS a difference, and §80's paid batch remains the only instrument "
            "that can say whether the difference matters to a reader."
        ),
        "members": members,
        "rejected": rejected,
    }


# --------------------------------------------------------------------------------- extraction


def extract(args: argparse.Namespace) -> dict[str, Any]:
    """One forward pass per (text, readout); write mean-pooled residuals to a gitignored dump.

    The dump carries a digest manifest beside the vectors. That is not tidiness: RUNBOOK's rule
    is that a replay cache keys on text digest rather than on labels, because a cache keyed
    `(family, scene, side)` replays numbers computed on texts that no longer exist the moment a
    transform is edited. An activation dump is exactly that kind of cache — the vectors outlive
    the prose they were read from — so :func:`score` refuses to read one whose manifest does not
    match the fixtures currently on disk.

    The thermal governor is `cdg_battery`'s, imported rather than reimplemented: this box
    hard-shut-down at call 431 of that run, and 72/66 with a three-failure tolerance are the
    constants the shutdown paid for. This run is far shorter, and it is governed anyway.
    """
    import numpy as np
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    if not torch.cuda.is_available():  # pragma: no cover - a CPU run is minutes per pass
        raise SystemExit(
            "no CUDA device visible. This is the silent-success failure mode "
            "mirrorbench.models.preflight exists to refuse: a CPU run would produce numbers, "
            "slowly, that are not the ones recorded here. Run under the MirrorBench interpreter."
        )

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, revision=MODEL_REVISION, dtype=torch.bfloat16
    )
    model.to("cuda").eval()

    families = build_families()
    texts: dict[str, str] = {}
    for name, pairs in families.items():
        kept, _ = drop_degenerate(name, pairs)
        for pair in kept:
            texts[f"{name}|{pair.scene}|+"] = pair.positive
            texts[f"{name}|{pair.scene}|-"] = pair.negative

    keys = sorted(texts)
    store: dict[str, Any] = {}
    token_counts: list[int] = []
    started = time.time()
    with torch.no_grad():
        for readout in ("text_mean", "judge_last"):
            for key in keys:
                body = texts[key]
                prompt = body if readout == "text_mean" else JUDGE_PROMPT.format(text=body)
                encoded = tokenizer(prompt, return_tensors="pt", add_special_tokens=True)
                encoded = {name: value.to("cuda") for name, value in encoded.items()}
                call = time.time()
                hidden = model(**encoded, output_hidden_states=True, use_cache=False).hidden_states
                elapsed = time.time() - call
                token_counts.append(int(encoded["input_ids"].shape[1]))
                for layer in READOUT_LAYERS:
                    block = hidden[layer][0].float()
                    vector = block.mean(0) if readout == "text_mean" else block[-1]
                    store[f"{readout}|{layer}|{key}"] = vector.cpu().numpy().astype(np.float32)
                throttle(elapsed * args.rest_ratio / REST_RATIO, gpu_temperature())

    store[MANIFEST_KEY] = np.array(
        json.dumps({key: digest(text) for key, text in texts.items()}, sort_keys=True)
    )
    RESULTS.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.activations, **store)
    return {
        "model": MODEL_ID,
        "revision": MODEL_REVISION,
        "n_layers": N_LAYERS,
        "d_model": D_MODEL,
        "readout_layers": list(READOUT_LAYERS),
        "texts": len(keys),
        "vectors": len(store) - 1,
        "tokens_min": min(token_counts),
        "tokens_max": max(token_counts),
        "tokens_mean": round(statistics.fmean(token_counts), 1),
        "seconds": round(time.time() - started, 1),
        "gpu_c_after": gpu_temperature(),
        # Recorded rather than assumed: a run that says nothing about its governor cannot be
        # told apart afterwards from one that had none.
        "throttle": {
            "rest_ratio": args.rest_ratio,
            "pause_above_c": PAUSE_ABOVE_C,
            "resume_below_c": RESUME_BELOW_C,
            "source": "cdg_battery.throttle",
        },
        "dump": str(args.activations),
    }


# ----------------------------------------------------------------------------------- scoring


def _fold_scaled_deltas(
    positives: list[list[float]], negatives: list[list[float]]
) -> list[list[float]]:
    """Paired differences in units of the run's own spread, one row per scene.

    Scaling is by the population sd of every text in the family — the same construction
    `repair_generation.feature_scale` uses, so a P0 number here is in the units §85 reports
    register movement in. It is deliberately NOT fitted inside the fold: the scale is a property
    of the family's texts and carries no label, so using all of them leaks nothing about which
    side is which. What must never cross the fold is the *direction*, and that is fitted on
    training scenes only inside :func:`loso_signs`.
    """
    width = len(positives[0])
    everything = positives + negatives
    scale = [statistics.pstdev([row[i] for row in everything]) for i in range(width)]
    return [
        [
            (pos[i] - neg[i]) / scale[i] if scale[i] > 0 else 0.0
            for i in range(width)
        ]
        for pos, neg in zip(positives, negatives, strict=True)
    ]


def layer_max_null(per_layer: dict[int, list[list[float]]]) -> dict[str, Any]:
    """Null of `max(k)` across layers, with one flip vector applied to every layer at once."""
    layers = sorted(per_layer)
    groups = len(per_layer[layers[0]])
    matrices = {layer: gram(per_layer[layer]) for layer in layers}
    observed_per_layer = {layer: sum(signs_from_gram(matrices[layer])) for layer in layers}
    observed = max(observed_per_layer.values())
    at_least = 0
    for flips in product((1, -1), repeat=groups):
        if max(sum(signs_from_gram(matrices[layer], flips)) for layer in layers) >= observed:
            at_least += 1
    return {
        "groups": groups,
        "k_by_layer": {str(layer): observed_per_layer[layer] for layer in layers},
        "k": observed,
        "best_layer": max(observed_per_layer, key=lambda layer: observed_per_layer[layer]),
        "p_exact": round(at_least / 2 ** groups, 6),
        "null_size": 2 ** groups,
        "smallest_attainable_p": round(1.0 / 2 ** groups, 6),
    }


def baseline_row(pairs: list[Pair], names: tuple[str, ...], *, steelman: bool) -> dict[str, Any]:
    """One surface baseline on one family, through the identical pipeline and null."""
    positives = [[p0_features(pair.positive, steelman=steelman)[name] for name in names]
                 for pair in pairs]
    negatives = [[p0_features(pair.negative, steelman=steelman)[name] for name in names]
                 for pair in pairs]
    deltas = _fold_scaled_deltas(positives, negatives)
    row = exact_flip_null(deltas)
    row["unscoreable_pairs"] = unscoreable(deltas)
    row["features"] = len(names)
    return row


def _check_manifest(dump: Any, families: dict[str, list[Pair]]) -> str:
    """Is this dump the one these fixtures produced? Digests, not key names."""
    if MANIFEST_KEY not in dump.files:
        return "no manifest — dump predates the digest rule"
    recorded = json.loads(str(dump[MANIFEST_KEY]))
    expected: dict[str, str] = {}
    for name, pairs in families.items():
        kept, _ = drop_degenerate(name, pairs)
        for pair in kept:
            expected[f"{name}|{pair.scene}|+"] = digest(pair.positive)
            expected[f"{name}|{pair.scene}|-"] = digest(pair.negative)
    if recorded == expected:
        return "matches"
    missing = sorted(set(expected) - set(recorded))
    changed = sorted(key for key in set(expected) & set(recorded)
                     if expected[key] != recorded[key])
    return f"{len(missing)} texts missing, {len(changed)} texts changed since extraction"


def best_single_feature(pairs: list[Pair]) -> dict[str, Any]:
    """The strongest *single* surface feature on a family, as a post-hoc diagnostic.

    **Not part of any bar, and deliberately so.** The pre-registered baseline is a mean-difference
    direction over all 25 (or 28) features, and that estimator dilutes: averaging 25 z-scored
    deltas can score worse than one feature that carries the whole difference. So "the probe beat
    P0" can be an artifact of P0's aggregation rather than a limit of surface measurement, and a
    reader needs this column to tell those apart. It is computed after the fact and it may not be
    substituted into `beats_p0` for this run — that would be tightening a rule against numbers
    already seen, which is exactly what §81 refused to do. The corrected rule is declared in the
    ledger for the next run instead.
    """
    perfect: list[str] = []
    best_k = 0
    for name in P0_PLUS_NAMES:
        positives = [[p0_features(pair.positive, steelman=True)[name]] for pair in pairs]
        negatives = [[p0_features(pair.negative, steelman=True)[name]] for pair in pairs]
        row = exact_flip_null([[a[0] - b[0]] for a, b in zip(positives, negatives, strict=True)])
        best_k = max(best_k, row["k"])
        if row["k"] == len(pairs):
            perfect.append(name)
    return {"best_k": best_k, "perfect_single_features": perfect}


def score(args: argparse.Namespace) -> dict[str, Any]:
    """Score every family: two surface baselines, then the probe if a dump exists."""
    import numpy as np

    families = build_families()
    dump = None
    manifest_state = "absent"
    if Path(args.activations).exists():
        dump = np.load(args.activations)
        manifest_state = _check_manifest(dump, families)
        if manifest_state != "matches":
            raise SystemExit(
                f"activation dump does not match the fixtures on disk ({manifest_state}). "
                "Re-run --extract. Scoring a stale dump would compute a verdict from vectors "
                "read off texts that no longer exist, which is the failure the digest-keyed "
                "cache rule exists to refuse."
            )

    report: dict[str, Any] = {
        "pre_registration": PRE_REGISTRATION,
        "model": MODEL_ID,
        "revision": MODEL_REVISION,
        "readout_layers": list(READOUT_LAYERS),
        "activations_present": dump is not None,
        "manifest": manifest_state,
        "families": {},
    }

    for name, raw_pairs in families.items():
        pairs, dropped = drop_degenerate(name, raw_pairs)
        entry: dict[str, Any] = {
            "is_floor": name in FLOOR_FAMILIES,
            "groups": len(pairs),
            "dropped_identical_scenes": dropped,
            "positive_arm": raw_pairs[0].positive_arm,
            "negative_arm": raw_pairs[0].negative_arm,
            "p0": baseline_row(pairs, P0_NAMES, steelman=False),
            "p0_plus": baseline_row(pairs, P0_PLUS_NAMES, steelman=True),
            "p0_best_single_DIAGNOSTIC": best_single_feature(pairs),
        }
        if dump is not None:
            for readout in ("text_mean", "judge_last"):
                per_layer: dict[int, list[list[float]]] = {}
                for layer in READOUT_LAYERS:
                    positives, negatives = [], []
                    for pair in pairs:
                        stem = f"{readout}|{layer}|{name}|{pair.scene}"
                        positives.append(dump[f"{stem}|+"].tolist())
                        negatives.append(dump[f"{stem}|-"].tolist())
                    per_layer[layer] = _fold_scaled_deltas(positives, negatives)
                row = layer_max_null(per_layer)
                row["unscoreable_pairs"] = unscoreable(per_layer[READOUT_LAYERS[0]])
                entry[readout] = row
        report["families"][name] = entry

    report["verdict"] = verdict(report)
    report["b6_proposal"] = propose_b6(report)
    return report


def verdict(report: dict[str, Any]) -> dict[str, Any]:
    """Apply the pre-registered rules. Floors first; nothing above a broken floor is read."""
    alpha = PRE_REGISTRATION["alpha_uncorrected"]
    strict = PRE_REGISTRATION["alpha_family_wise"]
    families = report["families"]
    readouts = [r for r in ("text_mean", "judge_last") if report["activations_present"]]

    floor_breaks: dict[str, list[str]] = {}
    for readout in [*readouts, "p0", "p0_plus"]:
        broken = [
            name for name in FLOOR_FAMILIES
            if name in families and families[name].get(readout, {}).get("p_exact", 1.0) <= alpha
        ]
        if broken:
            floor_breaks[readout] = broken

    identity = families.get("placebo_identical", {})
    identity_sane = all(
        identity.get(channel, {}).get("k", -1) == 0
        for channel in ["p0", "p0_plus", *readouts]
        if channel in identity
    )

    cleared: dict[str, list[str]] = {readout: [] for readout in readouts}
    cleared_family_wise: dict[str, list[str]] = {readout: [] for readout in readouts}
    closed_to_p: list[str] = []
    for name, entry in families.items():
        if entry["is_floor"]:
            continue
        surface_k = max(entry["p0"]["k"], entry["p0_plus"]["k"])
        if min(entry["p0"]["p_exact"], entry["p0_plus"]["p_exact"]) <= alpha:
            closed_to_p.append(name)
        for readout in readouts:
            row = entry[readout]
            beats_surface = row["k"] > surface_k
            if row["p_exact"] <= alpha and beats_surface:
                cleared[readout].append(name)
            if row["p_exact"] <= strict and beats_surface:
                cleared_family_wise[readout].append(name)

    primary = cleared.get("text_mean", [])
    return {
        "floor_breaks": floor_breaks,
        "identity_family_sane": identity_sane,
        "closed_to_p_surface_already_separates": closed_to_p,
        "cleared_and_beat_surface": cleared,
        # Both bars travel with the verdict rather than one being chosen once the numbers exist.
        # §81 recorded a threshold cleared by 0.011 on an interval spanning the null, and the
        # lesson it drew was that the strict rule has to be visible beside the loose one.
        "cleared_and_beat_surface_family_wise": cleared_family_wise,
        "replicated_primary": len(primary) >= 2,
        "reading": _reading(report, floor_breaks, identity_sane, primary, readouts),
    }


def _reading(
    report: dict[str, Any],
    floor_breaks: dict[str, list[str]],
    identity_sane: bool,
    primary: list[str],
    readouts: list[str],
) -> str:
    if not report["activations_present"]:
        return "BASELINES ONLY — no activation dump; run --extract before reading Track P."
    if not identity_sane:
        return (
            "VOID (BUG): the byte-identical placebo family did not return k=0. Something in the "
            "pipeline separates identical strings; no number in this file may be read."
        )
    if floor_breaks:
        return (
            "VOID ON FLOOR: " + json.dumps(floor_breaks, sort_keys=True) + " — a sham or placebo "
            "family cleared its null, so separation on the arms above it is not attributable to "
            "the named difference. Pre-registered outcome, not a corrected number."
        )
    if len(primary) >= 2:
        return (
            "TRACK P POSITIVE (primary readout, replicated on "
            + ", ".join(sorted(primary))
            + "). Discrimination only — no preference and no licence (§82). Fixture family B6 "
            "may be PROPOSED; only the operator may admit it."
        )
    if len(primary) == 1:
        return (
            f"UNREPLICATED: {primary[0]} alone cleared and beat surface on the primary readout. "
            "The pre-registered rule requires two. Proposes nothing."
        )
    return (
        "PERCEPTION-LIMITED AT 4B on the primary readout: no non-floor family cleared its null "
        "and beat both surface baselines. Kill condition met; record the negative and close, "
        "with the quadrant's second row standing as the finding."
    )


# -------------------------------------------------------------------------------------- cli


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--extract", action="store_true",
                        help="run the forward passes and write the activation dump (needs CUDA)")
    # Defaults to the value `cdg_battery` measured safe on this box rather than to something
    # faster. The card took the machine down mid-run once; four minutes is not worth relitigating.
    parser.add_argument("--rest-ratio", type=float, default=REST_RATIO,
                        help="duty-cycle rest as a multiple of call time; this box runs hot")
    parser.add_argument("--activations",
                        default=str(RESULTS / "latent-taste-activations.npz"))
    parser.add_argument("--out", default=str(RESULTS / "latent-taste-probe.json"))
    parser.add_argument("--fixtures-only", action="store_true",
                        help="print the fixture table and exit; no model, no scoring")
    args = parser.parse_args(argv)

    if args.fixtures_only:
        for name, raw_pairs in build_families().items():
            pairs, dropped = drop_degenerate(name, raw_pairs)
            flag = " FLOOR" if name in FLOOR_FAMILIES else ""
            print(f"{name:28s} G={len(pairs):2d} dropped={dropped}{flag}")
        return 0

    # Scoring is cheap and re-run often; extraction is the GPU pass and happens once. Carrying
    # the previous file's provenance forward keeps a re-score from silently deleting the only
    # record of which weights, how many tokens and what temperature produced the vectors.
    report: dict[str, Any] = {}
    existing = Path(args.out)
    if existing.is_file():
        prior = json.loads(existing.read_text(encoding="utf-8"))
        if "extraction" in prior:
            report["extraction"] = prior["extraction"]
    if args.extract:
        report["extraction"] = extract(args)
        print(json.dumps(report["extraction"], indent=2))

    report.update(score(args))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print("\nREADING:", report["verdict"]["reading"])
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
