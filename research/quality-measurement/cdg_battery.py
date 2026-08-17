"""Run the CDG battery: `surprisal.py` scored by `evaluate.py` over `ablate.py`'s ground truth.

The three modules were built for exactly this run and it had never happened: `results/` held
baseline and conversion numbers and no CDG ones, which BRIEF.md §3 records as "built and not
yet evidenced". This is the thin committed driver — every methodological choice lives in the
three instruments; what belongs here is only *which* chapters, and that is worth its own
docstring because chapter selection is where a confound would enter.

**Scored set: 30 chapters spread evenly over positions 1-90 of Mother of Learning.** Spread
rather than contiguous so no single arc of the book is the whole sample; capped at position 90
so the control material below is never a scored chapter or its neighbour, which
`surprisal.make_scorer` requires of the foreign source.

**Foreign prefix: chapter at index 100. Transplant donors: eight chapters from the 90s.** Both
from the same book, which is the deliberate, stricter choice `make_scorer`'s docstring argues:
the model keeps this author, this cast and this genre in the control condition, so the gain
isolates *this chapter's own* setup. The transplant donor being same-book makes that degrader
harder to detect than the "different story" its docstring imagines — a graft from thirty
chapters later matches the host's register exactly — so a detection here understates the easy
case rather than overstating it. `evaluate.selftest` set the precedent (donors 60-68 for
chapters 0-8).

**A minimum length of 4,500 words** on scored chapters, because `sentence_deletion` at full
dose must leave a text long enough for one prefix+block stride (1,536 tokens); a chapter that
shrinks below it would score NaN, and a NaN entering `evaluate`'s AUC lists would corrupt the
ordering silently rather than fail. Only three of 108 chapters are under the floor and all
three sit in the reserved tail, so in practice this excludes nothing; the raw log counts NaNs
anyway and the summary refuses to report a verdict over any.

**Every scorer call is logged to `results/cdg-raw.jsonl` with its (chapter, ablation, dose)**,
recovered by hashing the variant text against a map built from the same deterministic
`ablate.variants` call `evaluate` makes. The battery costs ~40 GPU-minutes; the raw log is what
lets the next question (per-ablation dose curves, sham asymmetry, a different AUC cut) be
answered from disk instead of from another run.

**The raw log is also the resume point, and that stopped being hypothetical.** The first
attempt at this run took the machine down at call 431 of ~1,010 — a thermal shutdown, not a
software fault. On startup the runner replays every parseable line of an existing
`cdg-raw.jsonl` into an in-memory cache and serves those calls without touching the GPU, which
works because both the ablations (seeded from the text) and the scorer (greedy forward passes)
are deterministic: the replayed number is the number that call would produce. A truncated
final line — the shape a power loss leaves — is dropped and the file rewritten clean before
new records append.

**The cache is keyed by a digest of the exact text scored, not by `(unit, ablation, dose)`.**
The triple was the first key, and it holds a claim the log cannot back: that the transform
which produced a variant is the transform in `ablate.py` *today*. Edit an ablation and every
one of its logged numbers describes text that no longer exists in the schedule — served by
triple, they replay as if nothing changed, and the run completes carrying measurements of
code that was fixed precisely because it was wrong. Keyed by text digest, an edited ablation
misses the cache for exactly its own variants and hits it for everything else. The first use
was real: the `rename_entities` stopword fix invalidated that sham's 120 records and replayed
the other 842.

**And the run is paced so there is no second shutdown.** Two mechanisms, both software-only
because a driver-level power cap needs an elevated shell this runner should not assume:

- **Duty cycle.** After every scored call the runner sleeps `REST_RATIO` times as long as the
  call took, cutting sustained board power roughly in half at `1.0`. Heat that trips a
  shutdown is accumulated average draw, not any single forward pass.
- **Temperature governor.** GPU temperature is read after every call (nvidia-smi; ~0.1s
  against ~1.4s calls); at or above `PAUSE_ABOVE_C` the runner idles until the card cools to
  `RESUME_BELOW_C`. The hysteresis gap is what makes it settle instead of oscillating at the
  threshold. A machine whose sensors this cannot read runs un-governed rather than not at all,
  and says so once on stderr.

Run offline with the MirrorBench interpreter (torch + CUDA); never from the loop:

    C:/DEV/MirrorBench/.venv/Scripts/python.exe cdg_battery.py
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from ablate import ALL, variants  # noqa: E402
from corpus_io import Unit, mol_chapters  # noqa: E402
from evaluate import auc, evaluate  # noqa: E402
from surprisal import BLOCK_TOKENS, DEFAULT_MODEL, PREFIX_TOKENS, make_scorer  # noqa: E402

N_SCORED = 30
SCORED_BELOW = 90
MIN_WORDS = 4500
FOREIGN_INDEX = 100
#: Even indices from the reserved tail, skipping the foreign chapter and the sub-floor tail
#: chapters (103, 105, 107 — the only three under the length floor in the book).
DONOR_INDICES = (90, 92, 94, 96, 98, 102, 104, 106)

#: Sleep this multiple of each call's duration after it. Measured on this machine: at 1.0 the
#: card climbed 60→72°C in about eight calls and cooling holds ate the wall clock (~1.3
#: calls/min effective); at 3.0 it settles at a 70-72°C equilibrium — brushing the pause line,
#: which says this case's cooling is weak, but holds become short top-ups instead of drains.
#: The run that finishes an hour later beats the one that takes the machine down at call 431.
REST_RATIO = 3.0
#: Pause/resume temperatures in °C, with hysteresis. 72 sits well under both the card's
#: throttle point and whatever tripped the shutdown. Resume was first set at 60 and measured
#: wrong for this box: with the under-load equilibrium at 70-72, draining a heat-soaked case
#: to 60 costs minutes per hold, while the first few degrees come back in seconds. 66 keeps
#: the band tight around the measured curve — peak unchanged, holds short.
PAUSE_ABOVE_C = 72
RESUME_BELOW_C = 66
POLL_SECONDS = 5.0


def gpu_temperature() -> int | None:
    """Current GPU core temperature, or None on a machine this cannot read."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10, check=True,
        )
        return int(out.stdout.strip().splitlines()[0])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None


def load_prior(path: Path) -> list[dict[str, object]]:
    """Parseable records from an earlier interrupted run, oldest first.

    Tolerant of exactly one kind of damage: a truncated final line, which is what dying
    mid-write leaves. Anything unparseable is dropped rather than repaired — a record that
    cannot be read back is a record the run has to redo, and redoing is cheap.
    """
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def scored_units(chapters: list[Unit]) -> list[Unit]:
    eligible = [unit for unit in chapters[:SCORED_BELOW] if unit.words >= MIN_WORDS]
    if len(eligible) < N_SCORED:
        raise SystemExit(f"only {len(eligible)} eligible chapters for a {N_SCORED}-chapter run")
    picked = [eligible[round(i * (len(eligible) - 1) / (N_SCORED - 1))] for i in range(N_SCORED)]
    if len({unit.unit_id for unit in picked}) != N_SCORED:  # rounding collision
        raise SystemExit("chapter selection produced duplicates; widen the eligible set")
    return picked


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def throttle(elapsed: float, temperature: int | None) -> None:
    """Rest after a call, then hold while the card is hot. See the module docstring."""
    time.sleep(REST_RATIO * elapsed)
    if temperature is None or temperature < PAUSE_ABOVE_C:
        return
    print(
        f"      gpu at {temperature}C; holding until below {RESUME_BELOW_C}C",
        file=sys.stderr, flush=True,
    )
    # Three consecutive failed reads end the hold: un-governed beats hanging on a dead
    # sensor, but the first version bailed on *one* — and a single transient nvidia-smi
    # hiccup was measured cancelling a cooldown at 69°C that should have run to 66.
    failures = 0
    while True:
        time.sleep(POLL_SECONDS)
        temperature = gpu_temperature()
        if temperature is None:
            failures += 1
            if failures >= 3:
                return
            continue
        failures = 0
        if temperature < RESUME_BELOW_C:
            return


def main() -> None:
    chapters = mol_chapters()
    scored = scored_units(chapters)
    donors = [chapters[i].text for i in DONOR_INDICES]
    foreign = chapters[FOREIGN_INDEX]

    # The same (text, donor) pairing `evaluate` will iterate, precomputed so the wrapper can
    # attribute each opaque scorer call. Determinism is load-bearing: `ablate` seeds every
    # transformation from the text itself, so regenerating variants reproduces them exactly.
    variant_of: dict[str, tuple[str, str, float]] = {}
    for index, unit in enumerate(scored):
        donor = donors[index % len(donors)]
        for key, _sign, _item, dose, text in variants(unit.text, donor=donor):
            variant_of[digest(text)] = (unit.unit_id, key, dose)

    results_dir = HERE / "results"
    results_dir.mkdir(exist_ok=True)
    raw_path = results_dir / "cdg-raw.jsonl"
    # Keyed by text digest — see the module docstring. A record without one predates the
    # digest field and cannot prove which text it scored, so it is redone rather than trusted.
    prior = load_prior(raw_path)
    prior_by_digest: dict[str, dict[str, object]] = {
        str(r["digest"]): r for r in prior if "digest" in r
    }
    undigested = len(prior) - len(prior_by_digest)
    raw_records: list[dict[str, object]] = []
    gpu_calls = 0
    if prior_by_digest:
        print(f"resuming: {len(prior_by_digest)} variants replayable from {raw_path.name}",
              file=sys.stderr, flush=True)
    if undigested:
        print(f"dropping {undigested} pre-digest record(s); they cannot prove which text "
              "they scored", file=sys.stderr, flush=True)
    if gpu_temperature() is None:
        print("GPU temperature unreadable; running un-governed", file=sys.stderr, flush=True)

    print(f"loading {DEFAULT_MODEL} ...", file=sys.stderr, flush=True)
    score = make_scorer(foreign.text)
    started = time.time()

    # "w" deliberately: replayed records re-append below in call order, which is also what
    # drops the truncated tail line an interrupted run leaves.
    with raw_path.open("w", encoding="utf-8") as raw:

        def persist(record: dict[str, object]) -> None:
            raw_records.append(record)
            raw.write(json.dumps(record) + "\n")
            raw.flush()

        def logged(text: str) -> float:
            nonlocal gpu_calls
            text_digest = digest(text)
            unit_id, key, dose = variant_of.get(text_digest, ("unmapped", "unmapped", -1.0))
            replay = prior_by_digest.pop(text_digest, None)
            if replay is not None:
                persist(replay)
                return float(replay["cdg"])  # type: ignore[arg-type]
            begun = time.time()
            value = score(text)
            elapsed = time.time() - begun
            gpu_calls += 1
            temperature = gpu_temperature()
            record = {
                "unit": unit_id,
                "ablation": key,
                "dose": dose,
                "digest": text_digest,
                "cdg": value,
                "words": len(text.split()),
                "seconds": round(elapsed, 2),
                "gpu_temp": temperature,
            }
            persist(record)
            print(
                f"[{len(raw_records):4d}] {unit_id:<8} {key:<20} @{dose:.2f}"
                f"  cdg={value:+.4f}  ({record['seconds']}s, {temperature}C)",
                file=sys.stderr,
                flush=True,
            )
            throttle(elapsed, temperature)
            return value

        result = evaluate(
            logged,
            [unit.text for unit in scored],
            metric="craft.cdg.v0",
            donors=donors,
            direction=-1,
        )

    nan_count = sum(1 for record in raw_records if math.isnan(record["cdg"]))  # type: ignore[arg-type]
    unmapped = sum(1 for record in raw_records if record["unit"] == "unmapped")

    # Per-ablation *pooled* AUC against the originals (above 0.5 = variants of this ablation
    # score below their originals). A between-chapter diagnostic, deliberately coarser than
    # `detect_auc`'s within-chapter statistic — chapter-level differences enter it, which is
    # acceptable in a per-ablation readout and not in a headline. For a sham this should sit
    # at 0.5, and reporting the two shams separately is the point: `rename_entities` is the
    # memorisation control and `respell` the token-novelty one, and a pooled sham number would
    # let a large effect in one hide behind a null in the other.
    originals = [
        record["cdg"]
        for record in raw_records
        if record["ablation"] == "original" and not math.isnan(record["cdg"])  # type: ignore[arg-type]
    ]
    per_key: dict[str, dict[str, float]] = {}
    for ablation in ALL:
        scores = [
            record["cdg"]
            for record in raw_records
            if record["ablation"] == ablation.key and not math.isnan(record["cdg"])  # type: ignore[arg-type]
        ]
        if not scores:
            continue
        per_key[ablation.key] = {
            "n": len(scores),
            "sign": ablation.sign,
            "auc_vs_original": auc(originals, scores),  # type: ignore[arg-type]
            "mean": round(sum(scores) / len(scores), 5),  # type: ignore[arg-type]
        }

    summary = {
        "metric": "craft.cdg.v0",
        "model": DEFAULT_MODEL,
        "block_tokens": BLOCK_TOKENS,
        "prefix_tokens": PREFIX_TOKENS,
        "direction": -1,
        "n_chapters": result.n_chapters,
        "scored_units": [unit.unit_id for unit in scored],
        "donor_units": [chapters[i].unit_id for i in DONOR_INDICES],
        "foreign_unit": foreign.unit_id,
        "scorer_calls": len(raw_records),
        "gpu_calls": gpu_calls,
        "replayed_calls": len(raw_records) - gpu_calls,
        "nan_scores": nan_count,
        "unmapped_calls": unmapped,
        "minutes": round((time.time() - started) / 60, 1),
        "throttle": {
            "rest_ratio": REST_RATIO,
            "pause_above_c": PAUSE_ABOVE_C,
            "resume_below_c": RESUME_BELOW_C,
        },
        "original_cdg_mean": round(sum(originals) / len(originals), 5) if originals else None,
        "detect_auc": result.detect_auc,
        "sham_auc": result.sham_auc,
        "margin": result.margin,
        "length_auc": result.length_auc,
        "paired_rate": result.paired_rate,
        "paired_ci": list(result.paired_ci),
        "paired_n": result.paired_n,
        "per_ablation_dose": result.per_ablation,
        "per_ablation_auc": per_key,
        "notes": result.notes,
        # The module docstring promises the summary refuses to report a verdict over NaNs;
        # the first version printed a warning and wrote the verdict anyway, which is the
        # combination nobody reads twice. A NaN entered the AUC sorts, so every number above
        # is suspect and the verdict line must not be quotable without saying so.
        "verdict": (
            result.verdict()
            if nan_count == 0
            else f"NO VERDICT — {nan_count} NaN score(s) entered the AUC lists; every number "
            "in this summary is suspect until the NaNs are explained"
        ),
    }
    out = results_dir / "cdg.json"
    out.write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")

    print(f"\n{summary['verdict']}", file=sys.stderr)
    print(f"written to {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
