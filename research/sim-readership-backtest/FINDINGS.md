# Findings — the sim-readership backtest

House form: the claim, the number beside it, and the caveat travelling with the claim. Every
arm is listed, run or not; an absence is marked, never silent (§89's rail).

## Status

The programme is **built, registered, and unspent**: PREREG.md reached REGISTRATION with every
slot filled from free runs, all seven modules are committed with hermetic tests, and the
driver's paid stages stand behind an explicit operator gate. **No model has been asked
anything; no arm below has a behavioural number.**

## Free findings (each already recorded in PREREG.md where it binds)

- **The corpus carries the design.** 2,014 divergent pairs at the registered floor across the
  twelve local shards (963 in `undeclared_2025`), against a power target of 200 decided
  pairs. Caveat: the pair count precedes the recognition screen, whose attrition is unmeasured
  until probes run.
- **The cutoff-clean confirmatory set is empty.** Zero pairs have both members first released
  on or after 2025-08-01 (the panel model's documented training cutoff is July 2025); the
  crawl predates the horizon. The confirmatory set is therefore recognition-clean
  `undeclared_2025` pairs, and the probe carries the entire memorisation defense. Caveat:
  this weakens the screen from two independent rails to one, stated in PREREG §3 with the
  corpus's obscurity (median one follower) as context, not weight.
- **Two sizing designs died before registration and are §8's findings**: the persona-grain
  two-way clustered bound has zero power at the population's registered heterogeneity, and an
  unconditional persona-redraw null converts draw variance into false clears (type-I
  0.21-0.34, rising with n). The registered primary is conditional on the frozen reward split
  for exactly this reason.
- **The conditional arithmetic is calibrated**: type-I 0.022-0.028 at every candidate size;
  power 0.826 at 200 decided pairs against a true 0.60.

## Arms

| arm | status | note |
|---|---|---|
| C-arm primary (continuation) | NOT_RUN | awaits the operator's go on the pilot |
| P-arm secondary (premise) | NOT_RUN | same gate |
| Recognition probes | NOT_RUN | precede every main-arm session, enforced in code |
| C1 sham pairs (n=12) | NOT_RUN | windows construction built and tested |
| C2 damage (same-book paragraph_shuffle) | NOT_RUN | transform certified elsewhere; direction untested here |
| C3 label shuffle | NOT_RUN | free once votes exist; deterministic replay |
| C4 surface confound | NOT_RUN | scan built; candidate count unmeasured until run |
| Positional VOID check | NOT_RUN | rule registered at the §120 precedent |

## Next decision

The pilot: ~20 confirmatory pairs, all controls live, inside the registered $180 ceiling with
its own PID lock and cost ledger, estimated by the driver's `plan("pilot", ...)`. It is the
programme's first paid call and the operator's one-bit gate applies; the driver refuses until
a commit cites that go.

## The pilot (stage b), run 2026-08-30/31 under the operator's go

**The gate refused the full stage, and both reasons are exactly what a pilot exists to buy.**
Record: `result-pilot.json` beside this file; raw cache `backtest-raw.jsonl` (1,104 records,
1 transport refusal). No VOID fired: positional deviation and the sham floor both sat under
the (degenerate) largest-true-effect, and the shuffle's clear share was 0.0. The recognition
screen came back **0 recognised of 40 books probed** — the corpus's obscurity carried it.

- **The cost basis was wrong by 2.09x.** Ledger $41.21 against the registered $19.68
  estimate; the 2x rule refused. At the measured per-pair price (~$2.06) the registered
  n=200 full run prices at ~$410 against the $180 programme ceiling — the ceiling is a
  refusal, so the full stage as registered cannot run. The correction and its options are
  the operator's (PREREG's K1a precedent governs any edit: it must name this number).
- **The C-arm under-ran by construction: 2 of 20 pairs bought sessions; 1 decided pair
  reached the primary.** The cache signature: pair one bought all 20 sessions (40 records),
  pair two bought 10 (20 records), pairs three through twenty bought nothing — their
  requests replayed earlier digests, ~~which is only possible if their stimuli were
  byte-identical to earlier ones~~ **corrected same day: the stimuli were fine (40/40
  distinct, 0 empty) — the cause was Windows' 32,767-character command-line ceiling in
  `elicit._call_cli`, which failed every oversized request at send, uncached and uncounted;
  the threshold predicts all 80 pilot cells with zero exceptions. Fixed by moving the prompt
  to stdin (commit 5006609), with three rails: degenerate stimuli refuse by name, an
  unanswered probe classifies `unprobed` (12 of 40 books had been certified clean by probes
  that never got through), and the result file carries an `under_run` block.** The P-arm ran
  all 20 pairs correctly (800 records, 400 votes) because its stimuli fit the ceiling.
  Nothing here reached a confirmatory number, so nothing is promoted or voided.

The verdict slot reads `refused` (2 outcomes < the registered minimum of 10), which is the
arithmetic refusing to manufacture a bound — the §85 rail working. Probes, P-arm and control
plumbing all ran end to end; every bought record replays free for any rerun.

## The re-pilot (stage b, second run), 2026-08-31, under the fixed transport

**Every arm ran to plan for the first time: zero transport failures, zero degenerate
stimuli, 400/400 C votes, and all 40 books really probed — 0 recognised.** Record:
`result-pilot.json`; cumulative ledger $175.05 (subscription-equivalent) against the raised
$900 ceiling, within 2x of the corrected estimate — the gate's cost half passes.

**The primary, descriptively (pilot n, no confirmatory claim): the reward split's aggregate
post-dicted the real market's retained member on 15 of 19 decided pairs (0.789), bootstrap
lower bound 0.579.** One pair undecided. Positional counterbalancing worked: within-order
first-position rates split 0.627 / 0.311 and cancel to a 0.035 deviation, far under the
void line. Shuffle clear-share 0.02, under its limit.

**Two control-arm corners fired, and both are design corners rather than verdicts:**

1. **The sham floor hit 0.5 off a two-vote sham.** Same-book window pairs draw heavy
   "neither" (sensibly), so decided-n per sham ran 2–14; the registered max-not-pooled
   floor is degenerate at n_decided=2 (any split is 0 or 1). The 0.5 floor exceeds the
   primary effect (0.289), so `void_sham` fired at the pilot's descriptive gate.
2. **The control arms are fixed-size and cache-frozen, so stage (c) would inherit these
   exact control outcomes by replay** — the sham void and the damage bound (11/15 intact
   preferred; lower bound 0.467 ≤ 0.5) are predetermined at full under the current
   constants. A confirmatory run whose control verdicts are decided in advance answers
   nothing.

**The honest path, stated before anyone likes an outcome:** any amendment (a minimum
decided-n for a sham to set the floor; stage-salted samples so controls draw fresh at (c);
larger control arms) is a post-hoc analysis change made after seeing data, and must be
recorded as such — justified mechanically (a two-vote sham cannot carry a floor), with the
full run reporting the original rule's verdict beside any amended one. The choice is the
operator's; nothing is amended in this entry, and stage (c) remains blocked by the
registered no-VOID gate until it is resolved.
