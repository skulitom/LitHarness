# Runbook — reproducing every number in the sim-readership backtest

PREREG.md is the registration; this file is how each of its numbers is reproduced from the
cached corpus and the committed code. Nothing here spends money except the explicitly marked
paid stages, and every paid number replays free from its cache afterwards.

## The two interpreters (the house split, unchanged)

Anything touching the parquet shards runs under the MirrorBench venv
(`C:/DEV/MirrorBench/.venv/Scripts/python.exe` — the only interpreter with pyarrow); anything
else runs under `uv run`. One sustained job at a time on this box — CPU jobs count
(CLAUDE.md's box rules).

## Free legs, in dependency order

1. **Corpus survey** (the PREREG §1 sizing numbers): the survey scripts are session
   artifacts; their outputs are quoted in PREREG §1 and §8. The registered pairing itself is
   `corpus.divergent_pairs` and reproduces via the pair build below.
2. **Pair build** (metadata pass, MirrorBench venv): group the twelve shards' rows per
   fiction (no `text` column loaded), `corpus.fiction_from_rows` each,
   `corpus.eligibility` census, `corpus.divergent_pairs` at the registered `min_ratio=3.0`.
   Deterministic: same shards, same pairs, same `pair_id`s.
3. **Excerpt pass** (MirrorBench venv): pull `text` for paired fiction ids only,
   `corpus.chapters_1_to_3` -> `blinding.blind` -> the content-addressed excerpt cache. Every
   downstream number cites these digests.
4. **Power table** (PREREG §8): exact binomial at the pair-bootstrap rejection rule; the
   table in §8 reproduces from its stated formula at z = 1.959964.
5. **Population**: `population.population_digest()` and the split lists print from
   `uv run python -c "import population; ..."` with the research directory on `sys.path`.

## Module map (PREREG §10)

- `corpus.py` — records, eligibility slugs (fixed order), cells, divergent pairing.
- `blinding.py` — identity stripping, `Blinded.digest` as the content address, `first_words`.
- `recognition.py` — frozen probe turns and deterministic hit scoring.
- `population.py` — the frozen personas, prompts, and the hash-assigned reward/holdout split.
- `arms.py` — session construction (describe-then-behave, both orders) and stage-2 parsing.
- `analysis.py` — aggregate accuracy, the pair-bootstrap primary interval, controls, VOIDs,
  and the assembled verdict.
- `backtest.py` — the staged driver (dry run / pilot / full), PID-locked, cost-ledgered.

## Paid stages (each gated on the previous; none run yet)

- **(a) dry run** — fake transport, plumbing only, spends nothing.
- **(b) pilot** — ~10% of target n, all controls live; proceeds only with no VOID fired and
  the ledger within 2x of estimate.
- **(c) full run** — one confirmatory look; everything after is exploratory and labelled.

Replays: the elicit cache is keyed by request digest **plus the sample index**
(`elicit._call`); pointing the driver's `--cache` at a prior raw JSONL reproduces any reported
number without a call.

Since PREREG's post-hoc amendment of 2026-08-31 that is true of the primary arms and the probes
but deliberately not of the control arms at stage (c): `backtest.control_stage_salt` puts the
stage name into the sample index for `sham`, `damage` and `surface`, so those cells re-draw
instead of replaying. Stage (b) keeps the empty salt, so the pilot's committed control numbers
still replay free from `backtest-raw.jsonl` — check that first if a pilot rerun starts spending.
A stage (c) result file carries two verdicts (`verdict_registered`, `verdict_amended`) and no
key called `verdict`.

## Tests

`uv run pytest tests/test_bt_corpus.py tests/test_bt_blinding.py tests/test_bt_recognition.py
tests/test_bt_population.py tests/test_bt_arms.py tests/test_bt_analysis.py
tests/test_bt_backtest.py -q` — hermetic, no shard, no call.
