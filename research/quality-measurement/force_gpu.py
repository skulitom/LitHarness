"""The inference contract every force shares: two pinned families, sampling, teacher forcing.

Separate from `force_harness` on purpose. The harness is arithmetic and imports no torch, so it
runs and selftests under either interpreter; this module is the only place a force touches a GPU,
and it runs **only** under the MirrorBench interpreter (`C:/DEV/MirrorBench/.venv/Scripts/
python.exe`), never `uv run python`. It imports no `litharness`.

**Three properties this module exists to guarantee, because a track re-implementing any of them
would be a track whose numbers cannot be compared with another track's.**

*Pinned weights.* Every load names a revision. `latent_probe` does this and `surprisal` does not,
and the difference matters the day a hub tag moves under a result file that only recorded a name.

*Seeded from the text.* :func:`sample_continuations` derives its generator seed from
`force_harness.text_seed`, so byte-identical input produces byte-identical output. That is what
buys `placebo_identical` the exact zero §89.4 gave it as a role; a placebo whose sides merely look
alike measures sampling noise and certifies nothing.

*Governed.* The thermal governor is `cdg_battery`'s, imported rather than reimplemented: this box
hard-shut-down at call 431 of that run, and 72/66 with a rest ratio are the constants the shutdown
paid for. Every call in this module goes through :class:`Governor`, and every result file records
the governor's settings — a run that says nothing about its governor cannot afterwards be told
apart from one that had none.
"""

from __future__ import annotations

import gc
import os
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


from cdg_battery import (  # noqa: E402
    gpu_temperature,
)
from force_harness import FAMILIES, text_seed  # noqa: E402

#: Rest ratio for this programme's long GPU runs.
#:
#: **This was 0.5 and it is 3.0 again, because the box went down on 2026-08-20 mid-F1.** The
#: reasoning for lowering it was that the temperature governor is the actual protection and the
#: rest ratio is only a coarse pre-emptive measure (RUNBOOK's own words) — and that reasoning
#: assumed the temperature governor was watching the sensor that matters. Every core reading this
#: session logged was 47-65 C against a 72 C pause, so the hold never fired and the box went down
#: anyway. A governor that never fires is not protection, and the coarse half was the half doing
#: the work. `cdg_battery`'s 3.0 is what a thermal shutdown already paid for once; paying for it
#: twice would be the more expensive kind of stubbornness.
DEFAULT_REST_RATIO = 3.0

#: Pause and resume on the **core**, and the *resume* number is the one that has now been wrong
#: twice on this box in the same way. §94's governor set resume at 60 and measured it wrong
#: because a heat-soaked case takes minutes to drain; this programme then set 58/52, and the
#: card's between-calls floor under sustained load is **53-58** — so the hold could almost never
#: release and exited on its five-minute timeout instead. Measured effect: F2 fell to eight
#: scored units in twenty minutes.
#:
#: A resume threshold must sit **just under the between-calls floor**, not far below it, or the
#: governor stops being a duty cycle and becomes a stall. 64/56 keeps real hysteresis, leaves
#: six degrees to the watchdog's 70 C kill, and lets work proceed.
PAUSE_ABOVE_C = 64
RESUME_BELOW_C = 56
POLL_SECONDS = 5.0

#: **The binding thresholds, and the measurement that produced them.**
#:
#: `temperature.gpu.tlimit` is *not* limit-minus-core, which is what it looks like at idle and
#: what the first version of this governor assumed. Traced on 2026-08-20 during F2:
#:
#:     t=  0s  core 46 C   margin 28 C     idle
#:     t= 60s  core 56 C   margin 20 C
#:     t= 70s  core 54 C   margin 12 C     <- core FELL, margin fell 8 C
#:     t= 80s  core 68 C   margin  4 C
#:
#: At t=70 s the core was cooler than at t=60 while the margin halved, so the two sensors are not
#: two views of one number. `tlimit` tracks the **hottest point on the die**, which runs far above
#: the core reading — and that is the whole explanation for three shutdowns whose core traces
#: looked comfortable. A governor watching the core was watching a sensor that stays calm while
#: the part that trips is not.
#:
#: So the hold is on margin, and recovery is **polled rather than slept**: a fixed multiple of the
#: call duration cannot know whether the hotspot has actually come back.
PAUSE_MARGIN_C = 14
RESUME_MARGIN_C = 20
MAX_HOLD_SECONDS = 120.0

#: The duty-cycle half of the recipe, and the half a per-call sleep cannot do. Per-call rest cools
#: the *die*; nothing in it clears heat from the case, and a run that holds the die at a
#: comfortable 60 C for six hours is still pouring several hundred watts into a closed box for six
#: hours. Every SOAK_EVERY calls the run stops for SOAK_SECONDS whatever the sensors say.
SOAK_EVERY = 25
SOAK_SECONDS = 90.0

#: Generation defaults, frozen here so two tracks cannot sample differently by accident.
TEMPERATURE = 0.8
TOP_P = 0.95

#: Seed cap in tokens, applied **symmetrically within a pair** by :func:`symmetric_seeds`.
#:
#: This is a confound the corpus carries and nobody had measured. §79 matched pairs on the
#: *source chapter's* word count (`taste_benchmark.MAX_LOG_WORD_GAP = 0.10`); the 1,000-word
#: **excerpt** was never matched, and on the real corpus 23 of 281 pairs differ by more than
#: 0.04 in |log10 word ratio| with a maximum of **0.4549 — one side 2.85x the other**. A silent
#: prompt truncation at a fixed ceiling therefore cuts one side and not the other, and a force
#: that reads seed length would score on the asymmetry. So the cap is per pair, both sides get
#: the same number of tokens, and what was cut is recorded rather than assumed to be nothing.
SEED_CAP_TOKENS = 1400

#: The longest sequence (prefix plus target) either pinned family will read in one pass.
#:
#: **Measured on this card, not inferred from the position limits.** Neither family has
#: flash-attention (not installed) or FlexAttention (needs Triton, absent on Windows), so SDPA
#: falls back to the math backend and materialises a `heads x L x L` attention matrix on every
#: full-attention layer:
#:
#:     gemma-3-4b   7,802 tok  12.9 GiB   1.2 s      qwen2.5-3b   7,801 tok  14.7 GiB    2.2 s
#:     gemma-3-4b  11,702 tok  18.6 GiB   1.1 s      qwen2.5-3b  11,701 tok  25.4 GiB   43.5 s
#:     gemma-3-4b  15,602 tok  26.5 GiB  12.3 s      qwen2.5-3b  15,601 tok  40.2 GiB  285.5 s
#:     gemma-3-4b  23,402 tok  48.8 GiB  71.5 s      qwen2.5-3b  19,501 tok  OOM
#:
#: Past ~20 GiB the allocator spills to host memory instead of failing, so an over-long pass does
#: not crash — it slows by two orders of magnitude. **Qwen binds first**: sixteen query heads to
#: gemma's eight is twice the matrix at equal length. 8,192 is where both stay resident and fast.
SINGLE_PASS_CEILING = 8192


def gpu_sensors() -> dict[str, Any]:
    """Core temperature, power draw and throttle reasons in one nvidia-smi call.

    `cdg_battery.gpu_temperature` reads the core only, and on 2026-08-20 this box went down
    during an F1 run whose **core never exceeded 65 C** — every sample this session logged was
    47-65, nowhere near the 72 C pause. So the core sensor is not the binding one and a governor
    watching only it was watching the wrong dial. What this reads instead:

    - `temperature.gpu` — the core, kept because it is still the cheapest early warning;
    - `temperature.gpu.tlimit` — **margin** to the card's own thermal limit in degrees, which is
      the number the card actually throttles on and is not recoverable from the core reading;
    - `power.draw` — a 4090 at a 382.5 W limit is the load a marginal supply trips on, and a
      whole-box shutdown with a cool core is a power event rather than a die-temperature one;
    - `clocks_event_reasons.*_slowdown` — the card saying it is already protecting itself, which
      is a fact and not an inference.

    Returns an empty-valued dict on a machine that cannot answer, so a caller degrades to the
    fixed duty cycle rather than crashing.
    """
    fields = (
        "temperature.gpu",
        "temperature.gpu.tlimit",
        "power.draw",
        "clocks_event_reasons.hw_thermal_slowdown",
        "clocks_event_reasons.sw_thermal_slowdown",
        "clocks_event_reasons.hw_power_brake_slowdown",
    )
    try:
        out = subprocess.run(
            ["nvidia-smi", f"--query-gpu={','.join(fields)}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=False,
        ).stdout.strip().splitlines()[0]
    except Exception:  # pragma: no cover - a box without nvidia-smi
        return {}
    parts = [p.strip() for p in out.split(",")]

    def number(value: str) -> float | None:
        try:
            return float(value)
        except ValueError:
            return None

    return {
        "core_c": number(parts[0]),
        "tlimit_margin_c": number(parts[1]),
        "power_w": number(parts[2]),
        "throttling": any(p.lower() in ("active", "true") for p in parts[3:6]),
    }


@dataclass
class Governor:
    """The rest-and-hold wrapper, plus the accounting a result file has to carry.

    **Hardened on 2026-08-20 after this box went down mid-run**, and the hardening is in three
    places rather than one because the post-mortem could not pin the cause on a single dial:

    1. `rest_ratio` defaults to `cdg_battery`'s **3.0** again. The force programme lowered it to
       0.5 (and one run used 0.25) to fit inside 40 GPU-hours, which is exactly the trade that
       turns a battery of a few hundred calls into hours of near-continuous load. Wall clock is
       cheaper than a shutdown that loses a run.
    2. The pause threshold drops to **65 C / 58 C resume**, below anything this session actually
       observed, so the hold fires before the card is anywhere near its own limit.
    3. A **soak break**: every `SOAK_EVERY` calls the run stops for `SOAK_SECONDS` regardless of
       temperature. Per-call rest cools the die; it does not clear heat from the case, and a
       run that keeps the die at 60 C for six hours is still pouring 380 W into a closed box.
       This is the duty-cycle half of the recipe, and it is the half a per-call sleep cannot do.

    Everything it observes is recorded, so a later run can tell a governed run from an ungoverned
    one instead of taking a docstring's word for it.
    """

    rest_ratio: float = DEFAULT_REST_RATIO
    pause_above_c: int = PAUSE_ABOVE_C
    resume_below_c: int = RESUME_BELOW_C
    pause_margin_c: int = PAUSE_MARGIN_C
    resume_margin_c: int = RESUME_MARGIN_C
    soak_every: int = SOAK_EVERY
    soak_seconds: float = SOAK_SECONDS
    hold_seconds: float = 0.0
    long_holds: int = 0
    calls: int = 0
    gpu_seconds: float = 0.0
    started: float = 0.0
    peak_core_c: float = 0.0
    peak_power_w: float = 0.0
    min_tlimit_margin_c: float = 999.0
    holds: int = 0
    soaks: int = 0
    throttle_events: int = 0
    samples: int = 0

    def __post_init__(self) -> None:
        self.started = time.time()

    def fold(self, sensors: dict[str, Any]) -> dict[str, Any]:
        """Record one reading and hand it back, so no call site can read without recording.

        **Every `gpu_sensors()` in this class goes through here.** The accumulators used to fold
        exactly one sample per call — taken *before* the rest sleep, i.e. at the coolest moment
        the governor ever observes — and the hold loop's three reads, which are by construction
        the hottest, folded none of them. Measured on a governed run: true minimum margin 7
        published as 13, true peak core 62 published as 54, and `throttle_events: 0` beside 8 of
        12 readings with the card's own throttle flag set. The thermal report was a summary of
        the moments the box was idle.
        """
        core = sensors.get("core_c")
        if core is not None:
            self.peak_core_c = max(self.peak_core_c, core)
        if sensors.get("power_w") is not None:
            self.peak_power_w = max(self.peak_power_w, sensors["power_w"])
        if sensors.get("tlimit_margin_c") is not None:
            self.min_tlimit_margin_c = min(self.min_tlimit_margin_c, sensors["tlimit_margin_c"])
        if sensors.get("throttling"):
            self.throttle_events += 1
        self.samples += 1
        return sensors

    def after(self, elapsed: float) -> None:
        self.calls += 1
        self.gpu_seconds += elapsed
        self.fold(gpu_sensors())

        time.sleep(elapsed * self.rest_ratio)

        # The hold. Binding on **margin to the card's own limit**, with the core and the card's
        # throttle flag as cheaper secondary triggers, and recovery polled rather than slept —
        # a fixed multiple of the call duration cannot know whether the hotspot has come back.
        hold_started = time.time()
        while True:
            sensors = self.fold(gpu_sensors())
            margin = sensors.get("tlimit_margin_c")
            core = sensors.get("core_c")
            # The margin sensor dips transiently — measured falling 13 C while the core fell 5 C
            # and the draw fell 200 W — so it is read twice before it is believed. The core and
            # the card's own throttle flag are trusted on one reading; `tlimit` is not.
            margin_low = margin is not None and margin <= self.pause_margin_c
            if margin_low:
                time.sleep(1.0)
                # `(... or 99)` here mapped **margin 0.0 — the card sitting on its own limit —
                # to 99**, and mapped a transient `nvidia-smi` failure to 99 as well. Both read
                # as "plenty of headroom" and cancelled the hold. Confirmed by running it: a
                # confirmation read of 3.0 held, 0.0 did not, `{}` did not. Every other sensor
                # test in this file and in `thermal_watch.py` uses `is not None`.
                confirm = self.fold(gpu_sensors()).get("tlimit_margin_c")
                margin_low = confirm is not None and confirm <= self.pause_margin_c
            hot = (
                margin_low
                or (core is not None and core >= self.pause_above_c)
                or bool(sensors.get("throttling"))
            )
            if not hot:
                break
            self.holds += 1
            self.hold_seconds += POLL_SECONDS
            if time.time() - hold_started > MAX_HOLD_SECONDS:
                # Recorded rather than ignored: a hold this long means the case is not clearing
                # heat at all, and continuing to poll silently would hide that from the report.
                self.long_holds += 1
                break
            time.sleep(POLL_SECONDS)
            cooled = self.fold(gpu_sensors())
            recovered_margin = (
                cooled.get("tlimit_margin_c") is not None
                and cooled["tlimit_margin_c"] >= self.resume_margin_c
            )
            recovered_core = (
                cooled.get("core_c") is not None and cooled["core_c"] <= self.resume_below_c
            )
            if recovered_margin and recovered_core:
                break

        if self.soak_every and self.calls % self.soak_every == 0:
            self.soaks += 1
            time.sleep(self.soak_seconds)

    def report(self) -> dict[str, Any]:
        wall = time.time() - self.started
        return {
            "rest_ratio": self.rest_ratio,
            "pause_above_c": self.pause_above_c,
            "resume_below_c": self.resume_below_c,
            "pause_margin_c": self.pause_margin_c,
            "resume_margin_c": self.resume_margin_c,
            "binding_sensor": "temperature.gpu.tlimit (hotspot margin), not core",
            "hold_seconds": round(self.hold_seconds, 1),
            "long_holds": self.long_holds,
            "soak_every_calls": self.soak_every,
            "soak_seconds": self.soak_seconds,
            "source": "force_gpu.Governor (hardened 2026-08-20 after a mid-run shutdown)",
            "calls": self.calls,
            "gpu_seconds": round(self.gpu_seconds, 1),
            "wall_seconds": round(wall, 1),
            "duty_cycle": round(self.gpu_seconds / wall, 3) if wall > 0 else None,
            "peak_core_c": self.peak_core_c,
            "peak_power_w": self.peak_power_w,
            "min_tlimit_margin_c": (
                None if self.min_tlimit_margin_c > 900 else self.min_tlimit_margin_c
            ),
            "holds": self.holds,
            "soaks": self.soaks,
            "throttle_events": self.throttle_events,
            # Published so a later reader can tell a report folded from every reading from one
            # folded from a single pre-sleep sample per call: `samples > calls` iff a hold fired.
            "sensor_samples": self.samples,
            "gpu_c_now": gpu_temperature(),
        }


_LOADED: dict[tuple[str, str], Any] = {}


def resolve(family: str, head: str = "base") -> tuple[str, str]:
    """(model_id, revision) for a family's head. Raises on a head that was never pinned."""
    spec = FAMILIES[family]
    key = head if head in spec else None
    if key is None:
        raise KeyError(f"family {family!r} has no head {head!r}; pinned heads: base, chat")
    return spec[head], spec[f"{head}_revision"]


def load(family: str, head: str = "base"):
    """Tokenizer and model at the pinned revision, on CUDA, in bfloat16.

    Refuses a CPU run loudly. A CPU fallback here would produce numbers — slowly — that are not
    the ones any result file in this directory records, which is the silent-success failure mode
    `latent_probe` already refuses in the same words.
    """
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    if not torch.cuda.is_available():  # pragma: no cover - a CPU run is minutes per pass
        raise SystemExit(
            "no CUDA device visible. Run under the MirrorBench interpreter: "
            "C:/DEV/MirrorBench/.venv/Scripts/python.exe"
        )
    model_id, revision = resolve(family, head)
    cached = _LOADED.get((model_id, revision))
    if cached is not None:
        return cached
    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
    model = AutoModelForCausalLM.from_pretrained(model_id, revision=revision, dtype=torch.bfloat16)
    model.to("cuda").eval()
    _LOADED[(model_id, revision)] = (tokenizer, model)
    return tokenizer, model


_TOKENIZERS: dict[tuple[str, str], Any] = {}


def load_tokenizer(family: str, head: str = "base"):
    """The tokenizer alone, without putting a model on the card.

    **This is what makes an interrupted GPU arm scoreable.** Every arm's scoring pass needs token
    *counts* — matched filler lengths, distractor flushes, probe offsets — and none of it needs
    weights. `load()` refuses without CUDA and occupies ~9 GB; on a shared box that means an arm
    whose run was interrupted could not be scored from its own cache without evicting whoever
    else is using the card. This path costs nothing and needs no GPU at all.
    """
    from transformers import AutoTokenizer

    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    model_id, revision = resolve(family, head)
    cached = _TOKENIZERS.get((model_id, revision))
    if cached is None:
        cached = AutoTokenizer.from_pretrained(model_id, revision=revision)
        _TOKENIZERS[(model_id, revision)] = cached
    return cached


def free() -> None:
    """Drop every loaded model. Two families at bf16 do not both fit beside a long context."""
    import torch

    _LOADED.clear()
    gc.collect()
    torch.cuda.empty_cache()


def pad_id(tokenizer: Any) -> int:
    """The pad token, or eos when there is none — and `is None` rather than `or`.

    Measured, not assumed: `gemma-3-4b-pt` has `pad_token_id == 0`, which is **falsy**, so the
    obvious `tokenizer.pad_token_id or tokenizer.eos_token_id` silently substitutes eos (1) for
    every gemma call. Harmless at batch size one and a corruption the day anything batches,
    which FX does.
    """
    return tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id


def symmetric_seeds(
    family: str,
    high: str,
    low: str,
    *,
    head: str = "base",
    cap: int = SEED_CAP_TOKENS,
) -> tuple[str, str, dict[str, Any]]:
    """Both sides of a pair cut to the SAME token count, with the cut recorded.

    `min(high_tokens, low_tokens, cap)` — so the shorter side is never padded, the longer side
    never enters with an advantage, and the ceiling still binds. The returned record carries the
    original token counts and the |log10 ratio| between them, which becomes a printed covariate
    rather than an invisible one: a pair whose sides differed 2.85x before the cut is a pair
    where any residual effect deserves the caveat.
    """
    high_tokens = count_tokens(family, high, head=head)
    low_tokens = count_tokens(family, low, head=head)
    keep = min(high_tokens, low_tokens, cap)
    import math

    record = {
        "seed_tokens_used": keep,
        "high_tokens_in": high_tokens,
        "low_tokens_in": low_tokens,
        "log10_token_ratio": round(abs(math.log10(high_tokens / max(low_tokens, 1))), 4),
        "truncated": bool(high_tokens > keep or low_tokens > keep),
        "cap": cap,
    }
    return (
        truncate_to_tokens(family, high, keep, head=head),
        truncate_to_tokens(family, low, keep, head=head),
        record,
    )


def context_limit(family: str, head: str = "base") -> int:
    """The family's hard token ceiling, read from its own config rather than remembered.

    Measured: `Qwen/Qwen2.5-3B` is **32,768** and `gemma-3-4b-pt` is 131,072. F3's longest
    condition sits near Qwen's ceiling, so the number has to be a fact the code can consult
    rather than a constant someone believed.
    """
    _, model = load(family, head)
    config = getattr(model.config, "text_config", model.config)
    return int(getattr(config, "max_position_embeddings", 32_768))


#: Measured on the pinned checkpoints, and recorded because it changes how a SPLIT_FAMILY on the
#: long-context arms must be read. `gemma-3-4b` interleaves 5 sliding-attention layers (window
#: 1,024) to every 1 full-attention layer; `qwen2.5-3b` is fully global to 32k. So at F2's
#: D = 8k and at every rung of F3's ladder, gemma routes long-range information through one
#: layer in six while Qwen routes it through all of them. **A disagreement between the two
#: families on those arms may be architectural rather than about prose**, and that reading is
#: pre-registered here rather than reached for afterwards.
ATTENTION_SHAPE = {
    "gemma-3-4b": {
        "sliding_window": 1024, "pattern": "5 sliding : 1 full", "max_positions": 131_072,
    },
    "qwen2.5-3b": {"sliding_window": None, "pattern": "full attention", "max_positions": 32_768},
}


def family_provenance(family: str, head: str) -> dict[str, str]:
    model_id, revision = resolve(family, head)
    return {
        "family": family,
        "head": head,
        "model_id": model_id,
        "revision": revision,
        "lineage": FAMILIES[family]["lineage"],
        "attention_shape": ATTENTION_SHAPE.get(family, {}),
    }


# ------------------------------------------------------------------------------- sampling


def sample_continuations(
    family: str,
    seed_text: str,
    *,
    k: int = 8,
    max_new_tokens: int = 512,
    head: str = "base",
    governor: Governor | None = None,
    max_prompt_tokens: int = 1600,
) -> list[str]:
    """K continuations of `seed_text`, each seeded from the text's own digest.

    **No instruction and no question.** The seed goes in as raw prose and the model continues it,
    which is the whole point of the programme: the measurement is what the text does to the
    generation field, not what the model says when asked. On the `chat` head a caller that wants
    an instruction builds the prompt itself and passes it here as `seed_text`.

    **The K replicates are generated as one batch, and the batch composition is a pure function
    of the text.** Batch composition changes reduction order in bf16 matmuls, so a replicate
    drawn inside a varying batch is not reproducible — but this batch never varies: it is always
    exactly `k` continuations of one prompt, so byte-identical text gives a byte-identical batch
    and byte-identical outputs. That is the property `placebo_identical` rests on, and it is
    verified on this exact path by `determinism_probe.py` rather than argued for here.

    Measured on this box: batching is 8.7x faster than looping (44s against 384s for eight
    512-token continuations from a 1,310-token prompt), which is the difference between F1 being
    affordable at full corpus and not.
    """
    import torch

    tokenizer, model = load(family, head)
    governor = governor or Governor()
    encoded = tokenizer(
        seed_text,
        return_tensors="pt",
        add_special_tokens=True,
        truncation=True,
        max_length=max_prompt_tokens,
    )
    encoded = {name: value.to("cuda") for name, value in encoded.items()}
    prompt_len = int(encoded["input_ids"].shape[1])
    # `generate` takes no `generator` argument in transformers 5.15 — checked in the signature
    # rather than assumed — so the process RNG is seeded immediately before the call. The seed
    # is a pure function of the text, which is the whole mechanism.
    seed = text_seed(seed_text, 0)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    call = time.time()
    with torch.no_grad():
        produced = model.generate(
            **encoded,
            do_sample=True,
            temperature=TEMPERATURE,
            top_p=TOP_P,
            max_new_tokens=max_new_tokens,
            min_new_tokens=max_new_tokens // 4,
            num_return_sequences=k,
            pad_token_id=pad_id(tokenizer),
        )
    governor.after(time.time() - call)
    return [tokenizer.decode(row[prompt_len:], skip_special_tokens=True) for row in produced]


# ------------------------------------------------------------------------- teacher forcing


def sample_batch(
    family: str,
    prompts: Sequence[str],
    *,
    max_new_tokens: int = 384,
    head: str = "chat",
    governor: Governor | None = None,
    max_prompt_tokens: int = 1600,
    add_special_tokens: bool = True,
) -> list[str]:
    """One continuation per prompt, all in a single left-padded batch.

    FX's chains need this shape: at each hop the R replicate chains hold *different* texts, so
    `num_return_sequences` on one prompt is the wrong tool and looping is four times the cost of
    a pilot that is meant to be cheap enough to kill.

    Determinism survives because batch composition is still a pure function of the inputs — the
    batch is exactly these prompts in this order, and the seed is the digest of them joined. Left
    padding rather than right, because a right-padded prompt would have the model generating from
    pad tokens.
    """
    import torch

    tokenizer, model = load(family, head)
    governor = governor or Governor()
    previous_side = tokenizer.padding_side
    tokenizer.padding_side = "left"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    encoded = tokenizer(
        list(prompts),
        return_tensors="pt",
        # FX passes False: `apply_chat_template` already emits the family's BOS, and tokenising
        # its output with `add_special_tokens=True` would prepend a second one. Measured on both
        # pinned chat heads rather than assumed.
        add_special_tokens=add_special_tokens,
        truncation=True,
        max_length=max_prompt_tokens,
        padding=True,
    )
    tokenizer.padding_side = previous_side
    encoded = {name: value.to("cuda") for name, value in encoded.items()}
    prompt_len = int(encoded["input_ids"].shape[1])
    seed = text_seed(" ".join(prompts), 0)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    call = time.time()
    with torch.no_grad():
        produced = model.generate(
            **encoded,
            do_sample=True,
            temperature=TEMPERATURE,
            top_p=TOP_P,
            max_new_tokens=max_new_tokens,
            pad_token_id=pad_id(tokenizer),
        )
    governor.after(time.time() - call)
    return [tokenizer.decode(row[prompt_len:], skip_special_tokens=True) for row in produced]


def chat_prompt(family: str, instruction: str, body: str, *, head: str = "chat") -> str:
    """The family's own chat template, rendered to a string so the caller stays transport-free.

    FX is the one track that instructs a model, so it is the one place a chat template appears.
    Rendering it here keeps the two families' templates out of the track's own code, where a
    hand-written approximation of one of them would be a silent difference between the families.
    """
    tokenizer, _ = load(family, head)
    return tokenizer.apply_chat_template(
        [{"role": "user", "content": f"{instruction}\n\n{body}"}],
        tokenize=False,
        add_generation_prompt=True,
    )


def token_logprobs(
    family: str,
    prefix: str,
    target: str,
    *,
    head: str = "base",
    governor: Governor | None = None,
    max_prefix_tokens: int = 30_000,
) -> tuple[list[float], list[int]]:
    """Per-token log-probabilities of `target`, conditioned on `prefix`. Nothing is sampled.

    Returns the per-token values rather than their mean, because F2 scores *committed sites*
    inside the target and a mean over everything would dilute twelve chosen tokens into six
    hundred unchosen ones. `surprisal._mean_logprob` is the same arithmetic with the mean already
    taken; this is that function with the reduction left to the caller, and with the revision
    pinned.

    Only target positions are scored. Including the prefix would make two conditions with
    different prefixes incomparable — the mechanical null `surprisal` was written to avoid.

    **`logits_to_keep` is not an optimisation here, it is the difference between running and
    not.** Gemma-3's vocabulary is 262,144 tokens, so the full-sequence logits for an 8k-token
    context are 262144 x 8192 x 4 bytes — about 8 GB in float32, on a 24 GB card that is already
    holding the model, and F2's longest condition is longer than that. `surprisal.py` gets away
    with materialising all of them because its sequences are 1,152 tokens; F2's are ten times
    that, and the check was made before the first pass rather than after an out-of-memory.
    """
    import torch

    tokenizer, model = load(family, head)
    governor = governor or Governor()
    prefix_ids = tokenizer(prefix, return_tensors="pt", add_special_tokens=True)["input_ids"][0]
    target_ids = tokenizer(target, return_tensors="pt", add_special_tokens=False)["input_ids"][0]
    if prefix_ids.shape[0] > max_prefix_tokens:
        prefix_ids = prefix_ids[-max_prefix_tokens:]
    # The scored block is the prefix's LAST token followed by the whole target, so the block's
    # position i predicts target token i and the arithmetic below is the same whether the rest of
    # the prefix arrived in one pass or in twenty. Everything before it is context and is only
    # ever needed as keys and values.
    ids = torch.cat([prefix_ids, target_ids]).unsqueeze(0).to(model.device)
    # **One pass, always, and a refusal rather than a fallback when it will not fit.** A chunked
    # prefill behind a KV cache was written here and then removed: on gemma-3 under transformers
    # 5.15 it does not reproduce a single pass (0.19 to 2.9 nats per token, through both the
    # multimodal wrapper and the inner text model, with an explicit cache class, explicit
    # `cache_position`, an explicit attention mask, at every chunk size). It sat behind a
    # `if context > chunk` branch for one hour, during which F3 silently computed 305 units
    # through it, because F3's contexts are 5-8k and the chunk was 2,048. A fallback that
    # changes the measurement is worse than a crash: the crash is visible.
    if int(ids.shape[1]) > SINGLE_PASS_CEILING:
        raise ValueError(
            f"{int(ids.shape[1])} tokens exceeds the {SINGLE_PASS_CEILING}-token single-pass "
            "ceiling. Shorten the caller's ladder; do not chunk, and do not raise this number "
            "without re-measuring attention memory on the card in front of you."
        )
    keep = int(target_ids.shape[0]) + 1
    call = time.time()
    with torch.no_grad():
        # `use_cache=False`: nothing is generated from this pass, so a KV cache is pure
        # allocation on a card that F2's longest condition already runs close to full.
        logits = model(ids, logits_to_keep=keep, use_cache=False).logits.float()
    governor.after(time.time() - call)
    # With `logits_to_keep=n` the returned block is the LAST n positions, so position -1 of the
    # block predicts nothing we score and the target's first token is predicted by block[0].
    window = logits[0, :-1, :]
    gold = ids[0, int(prefix_ids.shape[0]) :]
    picked = torch.log_softmax(window, dim=-1).gather(-1, gold.unsqueeze(-1)).squeeze(-1)
    out = [float(v) for v in picked]
    del logits, window, picked, ids
    torch.cuda.empty_cache()
    return out, [int(t) for t in target_ids]


def count_tokens(family: str, text: str, *, head: str = "base") -> int:
    tokenizer = load_tokenizer(family, head)
    return int(tokenizer(text, add_special_tokens=False, return_tensors="pt")["input_ids"].shape[1])


def truncate_to_tokens(family: str, text: str, tokens: int, *, head: str = "base") -> str:
    """Exact token-length matching. A 'length-matched' control matched in *words* is not one."""
    tokenizer = load_tokenizer(family, head)
    ids = tokenizer(text, add_special_tokens=False, return_tensors="pt")["input_ids"][0]
    return tokenizer.decode(ids[:tokens], skip_special_tokens=True)


def repeat_to_tokens(family: str, text: str, tokens: int, *, head: str = "base") -> str:
    """Own-generated filler, repeated deterministically until it reaches `tokens`.

    The distractor flush at D = 8k needs more tokens than any single own-generated scene holds.
    Repeating is declared rather than sampled: a random draw per call would make the control
    non-deterministic and its own re-runs incomparable, which is `surprisal`'s reasoning for
    fixed foreign offsets applied to a longer flush.
    """
    tokenizer = load_tokenizer(family, head)
    ids = tokenizer(text, add_special_tokens=False, return_tensors="pt")["input_ids"][0]
    if ids.shape[0] == 0:
        raise ValueError("empty filler text")
    reps = -(-tokens // int(ids.shape[0]))
    import torch

    stacked = torch.cat([ids] * reps)[:tokens]
    return tokenizer.decode(stacked, skip_special_tokens=True)


def selftest() -> int:
    """No GPU. Checks the wiring that can be checked without weights on the card."""
    failures: list[str] = []
    for family in FAMILIES:
        for head in ("base", "chat"):
            model_id, revision = resolve(family, head)
            if not model_id or len(revision) != 40:
                failures.append(f"{family}/{head} is not pinned to a 40-char sha")
    try:
        resolve("gemma-3-4b", "nonsense")
    except KeyError:
        pass
    else:
        failures.append("an unpinned head must raise rather than default")
    governor = Governor(rest_ratio=0.0)
    report = governor.report()
    for key in ("rest_ratio", "pause_above_c", "resume_below_c", "calls"):
        if key not in report:
            failures.append(f"governor report is missing {key}")
    for message in failures:
        print(f"FAIL {message}")
    print(f"force_gpu selftest: {len(failures)} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(selftest())
