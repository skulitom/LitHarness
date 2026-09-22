# Attainability: the call-free power record for arm `milder-v4`

**This record is call-free.** No model was called to produce it, and it simulates no reader from
first principles. It was commissioned by the coordinating session on 2026-09-22, run in that
session's scratch directory, and is copied here so the sizing that `PREREG.md` relies on lives in
the repository beside the registration. `PREREG.md` owns the design and the reading. This file
owns the sizing and says what the sizing rests on.

## What it rests on

1. **The real reader's sessions.** v2's and v3's committed per-session action records,
   `cost-that-bites/results-arm-v2.json` and `results-arm-v3.json`: 360 sessions of
   `claude-haiku-4-5` over `claude -p`, 20 books x 3 versions x 3 replicates per arm. The script
   recomputes every book mean from the raw actions and asserts that each one matches the
   committed `book_means` to 1e-9 before it uses any of them. Variance components are measured
   from those sessions. Nothing is taken from an idealised allocator, which is `BRIEF.md` §5's
   rule after §94.7 and §222.
2. **The shelf's texts.** The twenty fitness books, exported from scratch copies of
   `corpora/fitness/fitness-*.db` (their WAL files are empty, so the `.db` copies are complete).
   The chunk floor and the dose metrics are computed on these texts with `bcr.chunks`' own rule.
3. **An assumption the record cannot remove: how the effect scales with the dose.** No session
   has ever been bought at a partial dose, so the effect at s = 0.65 is written as
   `f(s) x 0.1765`, where 0.1765 is the mean of v2's +0.1640 and v3's +0.1890, and `f` is
   bracketed by four stated guesses rather than measured:

   | assumption | f at s = 0.65 | expected shift |
   | --- | --- | --- |
   | A4, convex (s squared) | 0.4225 | 0.075 |
   | A1, linear in strength | 0.65 | 0.115 |
   | A3, Kendall-distance ratio to the full shuffle | 0.7233 | 0.128 |
   | A2, broken-adjacency ratio to the full shuffle | 0.8788 | 0.155 |

   The arm measures one point on this curve. It does not test the curve.

## The files, and why two hashes each

The scratch originals were written with Windows line endings. The repository stores text with
LF (`.gitattributes`), so the copies here are the originals with CRLF replaced by LF and no
other byte changed. The scratch hash is what ran; the repository hash is what a checkout holds.

| file | scratch sha256 (CRLF, as run) | repository sha256 (LF) |
| --- | --- | --- |
| `attainability/milder_dose_power.py` | `9d0108374b4f723281464b32c1c81b3dbf349869e83eba59835d247ddad7692a` | `fb4c96f265cfd84a49d0ee71205f6d4145c223843da6dba0029cc04ad7aa9f51` |
| `attainability/results.json` | `27df846bf88e7f4b450343c1aab222dde59d0642927256e967529f1266540a73` | `21f2e5e5c66661c8e937ee69c99145c0110d94722e36f344715f00d53f38c1c7` |
| `attainability/noise_check.py` | `1250f3aed5c4990f6d10c2a8c2e8aac361bd6b8c8860cdbaaf84a7455522a848` | `1250f3aed5c4990f6d10c2a8c2e8aac361bd6b8c8860cdbaaf84a7455522a848` |
| `attainability/noise_check.json` | `c91484123300960b80e01aafb0927f9d172289b1d0de4b62b70f240f4f9d3290` | `30907208526a7eaa3eb581feac15199aad301cde741da4f0dfdb3ea5305a304f` |
| `attainability/export_texts.py` | `c2ee6d1570b9297b66f3bc467bde13c3c8b5509392761999f48c645e1ce9f10b` | `c2ee6d1570b9297b66f3bc467bde13c3c8b5509392761999f48c645e1ce9f10b` |
| `attainability/run.log` | `a07effecba03d59d052addb423bbc4e10c4702c4f463acbd67f97c6b1e688f66` | `4d4d0171732f89527b28d43dec2457d2141427e16cf4de2de0074a0cf06c437a` |

All six files are content-addressed in the registration (`cost_that_bites_milder.sources`), so
`verify` refuses a run if any of them changes after `prepare`.

`texts.json`, the power script's text input (1,277,531 bytes, sha256
`bd7020cd3a75cfc74484402c5af8678396e0de335dd3e3b7d434c6a392fb4250`), is **not committed**: it
holds the prose of the ignored local fitness stores and of other local-only books. It is rebuilt
by `export_texts.py` from store copies. `attainability/ruff.toml` exempts these files from
linting, because a record is not restyled after it has run.

To rebuild, copy `attainability/` to a scratch directory, put copies of the twenty fitness
stores in `fitness_copy/` beside it, and run `export_texts.py` and then `milder_dose_power.py`
there with `uv run python` (numpy is in the project environment). Both scripts hard-code the
repository path and write only beside themselves. The simulation seed is fixed (20260922), and
every simulated cell uses 1,000 trials, so a power figure carries a Monte Carlo standard error of
about 0.013.

## What it found

**The dose operator.** `ablate.paragraph_shuffle` is the wrong operator for a dose. It rotates
the picked paragraphs by one offset, so at strength 1.0 it makes a single cut: 0.7% of
adjacencies break. Its damage is not monotone in the strength: 0.28, 0.53, 0.61 and 0.007 of
adjacencies broken at s = 0.15, 0.35, 0.65 and 1.0. It is also one fixed variant per text. The
registered operator is a new seeded partial shuffle. It picks `round(s * n)` positions and gives
their contents a uniformly random non-identity permutation.

| operator (mean over 20 books x 10 seeds) | paragraphs displaced | adjacencies broken | Kendall distance |
| --- | --- | --- | --- |
| full shuffle (v2/v3) | 0.993 | 0.993 | 0.499 |
| **partial, s = 0.65** | **0.644** | **0.873** | **0.361** |
| partial, s = 0.35 | 0.343 | 0.570 | 0.211 |
| `ablate.paragraph_shuffle`, s = 0.65 | 0.650 | 0.613 | 0.288 |

Inside the reader's window (the first 11 chunks a session can reveal) the registered dose breaks
0.874 of adjacent pairs against the full shuffle's 0.993, a ratio of 0.88: it is much milder in
paragraphs moved than in joins broken where the reader looks. `PREREG.md` lists every candidate
the record computed (partial at 0.15, 0.35, 0.65 and 1.0; `ablate` at 0.15, 0.35, 0.65 and 1.0)
and why one was registered.

**The chunk floor.** A feed member needs 11 chunks. At s = 0.65 over seeds 0 to 9, exactly one
book and seed falls below it: `fitness-08` at seed 1, with 10 chunks. The seed rule must cover
it, and does: `fitness-08` takes seeds (0, 2, 3, 4, 5, 6). The full shuffle's known case
(`fitness-08` at seed 4) reproduces as a check.

**Power, twenty books, the registered statistic and interval.** The statistic is the book mean
of `target_read_share`, intact - dosed, with a 90% cluster bootstrap over books (2,000
resamples) whose lower bound must exceed 0. MOVES_WITH_ORDER also needs sham - dosed above 0.

| s = 0.65, assumption | 3 per version: parametric / constant-heterogeneity / resampled / analytic cross-arm | 6 per version: analytic within-arm / cross-arm | 6 per version, MOVES_WITH_ORDER (parametric) |
| --- | --- | --- | --- |
| A4, s squared (0.075) | 0.406 / 0.314 / 0.370 / 0.599 | **0.572 / 0.769** | 0.406 |
| A1, linear (0.115) | 0.686 / 0.605 / 0.600 / 0.803 | **0.860 / 0.899** | 0.774 |
| A3, Kendall (0.128) | 0.744 / 0.719 / 0.668 / 0.839 | 0.910 / 0.916 | 0.855 |
| A2, adjacency (0.155) | 0.858 / 0.815 / 0.751 / 0.890 | **0.969 / 0.939** | 0.948 |

At no effect (f = 0), **at three sessions per version** (the k = 3 grid,
`power_grid_by_attenuation["0.0"]`), the false-positive rate is 0.056 to 0.062 against a nominal
0.05, and the joint MOVES_WITH_ORDER rate is 0.016 to 0.018, so the reading is calibrated at
k = 3. The six-per-version simulation has no f = 0 row, so **calibration at six per version is
unmeasured**. The "6 per version" parametric
simulation gives 0.561, 0.860, 0.922 and 0.974 for these four rows, which agrees with the
analytic within-arm column. **At three sessions per version the linear case sits near 0.6 to 0.8,
and MOVES_WITH_ORDER near 0.5.** That is why the operator's approval is for six.

**s = 0.35 is not attainable at twenty books.** At six sessions per version the linear case
gives 0.451 / 0.682 and the s-squared case 0.133 / 0.223. Reaching 0.8 needs 28 to 53 books in
the linear case. The shelf holds twenty, so 0.35 is not registered.

## Where these numbers are optimistic, stated before spend

- **No resampled figure exists at six per version.** The resampling model draws real sessions,
  and only six exist per book and version across v2 and v3, so it cannot be run at k = 6. At
  k = 3 it ran 0.04 to 0.11 below the parametric figure (0.600 against 0.686 linear, 0.751
  against 0.858 adjacency). v2 recorded the same direction, with its normal approximation about
  0.05 optimistic. Read every six-per-version cell above as optimistic by a similar margin.
- **The two variance splits disagree about what replicates can buy.** Within-arm replicate
  spread gives effect heterogeneity tau^2 = 0.0145 and noise 0.0545 in a k = 3 paired
  difference. Cross-arm replication (v2 against v3, `noise_check.json`) gives tau^2 = 0.0463
  and noise 0.0227: more of the variance is real between-book difference, which replicates cannot
  remove. Per-book differences correlate 0.72 across the two arms, which also says heterogeneity
  is real. The analytic columns above assume that heterogeneity shrinks with the dose, as f
  squared.
- **Sensitivity added by this registration, not part of the record.** This is the same analytic
  formula with the record's own variance components, but with heterogeneity held constant
  (book differences in order sensitivity do not shrink with the dose). At six per version it
  gives 0.790 / 0.688 in the linear case, 0.863 / 0.768 for Kendall, 0.957 / 0.893 for
  adjacency, and 0.469 / 0.399 for s squared (within-arm / cross-arm). This is the pessimistic
  corner of the linear case, and it is still above the 0.6 that three per version would give.
- **v3's intact and sham sessions repeat v2's action sequences more often than chance**: 7 and 8
  of 60, against 2 of 60 for the shuffled sessions, with the same requests in separate caches.
  The reader is closer to deterministic in some cells than the within-cell variance suggests.

## Checked by this registration, call-free

- The registered `cost_that_bites_milder.partial_order` reproduces the record's `perm_partial`
  permutation exactly on 400 of 400 cases: 20 books x 10 seeds x s in {0.35, 0.65}. The
  operator that runs is the operator that was sized. The real-text check was run once, by hand;
  what stays pinned is `tests/test_cost_that_bites_milder.py`, which loads
  `attainability/milder_dose_power.py` by path and asserts the two agree on synthetic texts x
  10 seeds x {0.35, 0.65}.
- **Request identity, on the power record's texts:** this arm's 120 intact and sham sessions at
  replicates 0 to 2 replay 120 of 120 from v2's committed `raw-v2.jsonl`, opened replay-only,
  and reproduce v2's committed book means with a largest difference of 0.0. `prepare` repeats
  this on the texts it extracts and refuses to register if it fails.
- **The same reader against itself**, from the committed `results-arm-v2.json` and
  `results-arm-v3.json` on those same requests: v3 - v2 is +0.068 [+0.013, +0.126] on intact and
  -0.041 [-0.125, +0.044] on sham, and 7 and 8 of 60 sessions repeat v2's action sequence (2 of
  60 for the full shuffle, whose texts differed). This is the baseline the drift diagnostic is
  read beside, and the reason `PREREG.md` registers no drift rule.
- On the shelf's texts, the plan builds 360 cells with no fault. The minimum dosed chunk count is
  11, the only seed deviation is `fitness-08` (0, 2, 3, 4, 5, 6), and the mean dose over the 120
  dosed copies is 0.644 displaced and 0.873 broken.
- The seed rule's added clause, that a dosed opening must differ from the intact opening,
  changes no seed. On this shelf no partial copy at seeds 0 to 9, no full shuffle at seeds 0 to 9
  and no sham has an opening identical to its intact book's. The clause exists because the replay
  cache keys on the revealed prose, which a partial dose could in principle leave untouched
  (`PREREG.md`, "Seeds").

## What it cannot say

It cannot say whether the reader responds to a partial dose at all. That is the question the arm
buys. It sizes only against the variance a responding reader has already shown. It says nothing
about a Codex reader, for which no session exists (`PREREG.md`, "The Codex contingency"). It says
nothing about the current pipeline's books. The export found that they can carry a feed (the
connected-chapters books hold 14 to 15 chunks, `loadstitch` 38, full-book trial A1 171 or 172),
but a held-out set of six books would give 0.29 to 0.39 power at this dose, so none of them is in
this arm.
