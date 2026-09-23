# Results: arm `milder-v4a`, the costed reader at a partial dose

**Reading: MOVES_WITH_ORDER** (`results-milder-v4a.json`, from the registered `analyse`, run
once on 2026-09-23 at about 05:22). The claim moves from REGISTERED to **OBSERVED**
(`claim-v4a.json`). The PREREG's table makes it eligible for SUPPORTED on review; this file is
not that review.

## What was bought

All 360 sessions (20 fitness books x intact, partial-0.65, sham x 6 replicates), through the
§258-fixed transport, in two invocations. The first stopped at 144 sessions on the account's
session limit (`cli_error:rc=1:429 You've hit your session limit`, five calls, the first failure
cause this house has kept whole); the second, after the window reset, bought the rest with zero
transport failures. 2,923 calls, 97.4M reported tokens, **$69.35 equivalent**, 3 h 32 min of
calls. With milder-v4's contaminated purchase ($19.77, never read) the question has cost
**$89.12**, inside the operator's sign-off of $170 (AMENDMENT-1.md).

## Preconditions (all PASS)

| precondition | floor | measured |
| --- | --- | --- |
| request identity with v2's cache | every cell replays, same means | 120 of 120, largest book-mean difference 0.0 |
| scorable share | 0.75 | 1.0 in every version |
| position check (fp5) | 0.05 | 0.191 |
| slot-A capacity | 0.40 | 0.586 |
| books complete | 10 | 20 |

## The reading

Target read share, book means over six replicates, 90% cluster bootstrap over the 20 books:

| contrast | point | interval | |
| --- | --- | --- | --- |
| intact - partial | **+0.194** | [+0.134, +0.252] | above zero |
| sham - partial | **+0.199** | [+0.121, +0.275] | above zero |
| intact - sham | -0.005 | [-0.090, +0.082] | contains zero |

Both registered conditions hold, so the decision is MOVES_WITH_ORDER at s = 0.65 for a book in
slot A. Mean target read share: intact 0.649, sham 0.653, partial 0.455. The abandonment step
moves the same way (intact - partial +0.85 steps, [+0.42, +1.28]).

**Licence, as registered:** the reader reads a book less when 65% of its paragraphs are reordered
among themselves, beyond the whitespace sham, for a book in slot A, on this shelf and this
reader. Inside the reader's window the dose breaks 87% of adjacent pairs against the full
shuffle's 99% (a ratio of 0.88): a short step from destroyed order, not a book that is merely
worse. Not a quality instrument, not QUALIFIED, no editorial intervention.

## Reported beside the decision, deciding nothing

- **The effect did not attenuate.** The point estimate (+0.194) lies above the power record's
  attenuation bracket [0.075, 0.155] and matches the full shuffle's (+0.164 in v2, +0.189 in v3).
  At this dose the reader pays the whole-book price, which fits the adjacency assumption (87% of
  the pairs it can see are broken) better than the linear one. It says nothing yet about a dose
  a reader would call merely worse.
- **The reader drifted from v2's.** On byte-identical intact requests this run's reader read the
  target **+0.153 more** than v2's ([+0.061, +0.241]); on the sham requests it did not
  (-0.002, [-0.084, +0.077]). The same-reader baseline, v3 - v2 on identical requests, was
  +0.068 [+0.013, +0.126]. Two things changed between v2 and this run: the CLI (unrecorded for
  v2; 2.1.280 here) and the working directory (§258: v2 ran from the repository root, where the
  CLI could show it the repository's git status; this run ran from an empty temporary directory).
  The run cannot separate them, and the served model is not observed. So the table's clause
  **"if this run's reader is the one §230 measured, §230's claim extends that step" is not
  supported** by this run: the arm's own reading stands on its own reader, not as an extension
  of §230.
- Every scorable-share, skim and per-slot figure is in `results-milder-v4a.json`.

## What it does not establish

A quality instrument; QUALIFIED or any production authority; any reader but this one model and
CLI; that this reader is §230's; any shelf but twenty old house fitness books; sensitivity to a
milder or semantic defect (s = 0.35 was not attainable at this n, and the PREREG forbids choosing
another dose to hunt for movement).

## Artifacts

`raw-milder-v4a.jsonl` (the cache), `runs-milder-v4a.jsonl` (the ledger),
`failures-milder-v4a.jsonl`, `probes-milder-v4a.jsonl` (the three git probes and the marker
probe at each invocation's start), `results-milder-v4a.json`, `claim-v4a.json`,
`registration-v4a.json`. milder-v4's contaminated cache and ledger stay committed and unread.
