# Results: the model-tier comparison (`model-tiers.v1`)

**No tier change is proposed.** `gpt-6-luna` does not qualify to write scene summaries at
either effort, and the `gpt-6-sol` seed screen showed no gross failure, which by registration
licenses nothing. The claim is **OBSERVED** (`claim.json`); `results.json` owns every number.

## What was bought

172 of 172 planned Codex calls, all answered, in one invocation on 2026-09-23 (04:25 to 05:38
UTC): 2,397,019 reported tokens, 4,300 s of call time, no stop, no transport failure. Codex
reports no dollar cost.

## Scene summaries (basic tier, candidate `gpt-6-luna`)

The full-book trial's 24 recorded summary requests, replayed byte for byte (the recorded
wording) and rebuilt on today's §255 wording, on Luna at medium and at high effort against fresh
`gpt-6-astra` controls. Every outcome is computed in code; no model judged anything.

| test (scenes passing) | Luna medium | Luna high | Astra control |
| --- | --- | --- | --- |
| schema conformance | 24 / 24 | 24 / 24 | 24 / 24 |
| every evidence quote located once in the scene | 12-16 / 24 | 18 / 24 | 24 / 24 |
| paid promises match the accepted record | 8-9 / 24 | 17 / 24 | 23 / 24 |
| clean copy of the ledger's subjects (today's wording) | 23 / 23 | 23 / 23 | 23 / 23 |
| field agreement, today's wording (mean) | 0.52: **fail** | 0.69: inconclusive | 0.89 |
| field agreement, recorded wording (mean) | 0.63: inconclusive | 0.74: inconclusive | 0.79 |

Luna at high effort sits significantly below the Astra control on today's wording (difference
-0.20, 97.5% interval [-0.32, -0.08]), and at medium effort it fails outright. A candidate
passes only if every test passes; neither does, so `proposal` is null. Summaries feed later
drafting context, and the misplaced evidence quotes and wrong paid-promise calls are exactly the
errors that would travel. Scene summaries stay on the strong tier.

## World seed (standard tier, candidate `gpt-6-sol`), a screen

The trial's own pre-seed store, rebuilt byte for byte, seeded twice on Sol and twice on Astra
with today's request. Both Sol seeds came back clean through `world check`, `world accept` and
`world check` again, as did both Astra seeds; structural agreement 0.99 against Astra's 1.00.
Verdict: `no_gross_failure_seen`. As registered, two replicates a side cannot establish
reliability (a Sol that is clean 70% of the time looks clean in both draws 49% of the time), so
the screen licenses nothing; moving the Architect needs its own registration with enough
replicates, and covering grow, which is 7 of the Architect's 8 calls in a book.

## What it does not establish

Anything about quality (no prose field is scored, and agreement with Astra's record is not
correctness); any book but this trial's one; the post-§255 wording against an accepted record
(none exists, so that block reads Luna against a second Astra); whether a candidate reproduces
subjects it coined itself scenes earlier; the downstream effect on drafting; anything about the
Claude tiers.
