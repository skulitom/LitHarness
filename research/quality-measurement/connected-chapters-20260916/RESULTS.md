# Connected chapter experiences: completed result

Status: **OBSERVED** authoring demonstration, completed with an explicit budget continuation.
The original registration was committed and pushed as `c0fc1f2`, and its continuation as
`0f87f3e`, each before its live dispatch. Both arms used frozen production revision `79f4da7`.
See [RUNBOOK.md](RUNBOOK.md) and [CONTINUATION.md](CONTINUATION.md).

## Milestone and descriptive conclusion

All four three-chapter sequences were generated and read, including all concepts/discovery,
complete outlines, the rejected concept attempt, and every unique raw/accepted difference.
The local report locates both chapter transitions in every sequence, separating enacted
activity from future proposals, and records omissions and counterexamples. The deliverable
is complete; that does not imply that every sequence fulfills its proposed experiences.

Both workflows contain causal continuations. The B2 outline assigns D1, D2 and D3 to its
first three chapters, divides D5 across chapters 5–6, and defers D6–D8 beyond the six-chapter
outline. The supplied material reaches the planner intact. A distinct B2 source fact reaches
the writer but is not communicated in the three chapters. A1 also changes a proposed opening
event during outlining. Full narrative details and locations remain under ignored
`runs/connected-chapters-20260916/REPORT.md` and `READING-NOTES.md`, bound by
[reading-record.json](reading-record.json).

The observations motivate a possible isolated chapter-allocation comparison with fixed story
material, rather than another whole-workflow causal claim. B2 would be a disclosed diagnostic
case, not independent confirmation. No candidate ranking, quality score, validated intervention,
or production feedback is licensed. A separate observed actor/state mismatch in B2's planner
request warrants deterministic reproduction before a further live test; its code cause and
effect on scheduling have not been established by this reading.

## Execution and preservation

- Four completed books, twelve chapters, 18,672 words; each book has three chapters, an empty
  queue, no terminal jobs and zero unattributed revisions on store verification.
- 95 completed provider calls, 2,808,462 recorded tokens, zero unknown-usage calls.
  Elapsed time is 4,492.813967 seconds from original dispatch, including continuation preparation.
- Original run: 77 calls, 2,536,927 tokens, two chapters per book, then a token-ceiling stop.
  The last admitted call crossed the ceiling as permitted. The refused A2 grow2 step had no
  dispatched provider call and unchanged canonical metadata/job counts.
- Explicit continuation: 18 calls, 271,535 additional tokens; the aggregate token ceiling
  became 3.5 million while original call/time/per-book/phase limits remained. The preparation
  gap was 510.319832 seconds. Original call metadata and the earlier eight chapter hashes
  are preserved, along with closed stop snapshots and the refused step.
- World seed/grow phases used 2,252,442 recorded tokens. Phase totals are in
  [readout-controls.json](readout-controls.json); no dollar-cost or equal-cost comparison is made.

## Controls and ordinary retries

All transport, phase, first-invention-request, author/experience retention, and structured
projection controls pass. All 24 outline chapter coverage entries survive. All twelve full
scene briefs reach their writers and match stored job-bound plans and originating outlines.
There is one writer call and one policy attempt per chapter. Eleven raw drafts equal accepted
text; one differs only by the existing surface cleanup, and that difference was read in full.
There were no narrative repairs or manually selected continuations.

B2's ordinary concept invocation has two invention attempts: the existing lexical validator
rejected the first for an internal-vocabulary word appearing in a place name. The second was
saved; both are retained and read. Registration wording "first-draw" therefore means one
ordinary invocation retaining its automatic retries, not uniformly one raw concept response.
All four precision responses contain no edits. Baseline opening replacement from discovery
is retained and accounted for in the local raw comparison.

Readout revalidates 367 frozen files, 126 handoff source files and frozen continuation inputs.
These are execution and transmission controls, not evidence of narrative quality or semantic
fulfillment. Two premises, one ordinary invocation per workflow, one familiar premise,
independently invented concepts/worlds and divergent continuations prevent an isolated format
effect or a generalization to pleasure, popularity, complete books or long serials.

## Evidence and reproduction

- [evidence.json](evidence.json): calls, receipts, usage, stops, retention, reached books and controls.
- [handoff-evidence.json](handoff-evidence.json): outlines, stored plans and writer correspondence.
- [readout-controls.json](readout-controls.json): compact integrity, budget, usage and preservation.
- [reading-record.json](reading-record.json): read artifacts and local report hashes. Agent reading
  attestation does not promote the claim beyond OBSERVED.

With the completed local artifacts:

```powershell
uv run python research/quality-measurement/connected-chapters-20260916/continue.py audit
uv run python research/quality-measurement/connected-chapters-20260916/summarize.py
uv run python research/quality-measurement/epistemic_governance.py research/quality-measurement/connected-chapters-20260916/claim.json
uv run python research/quality-measurement/epistemic_governance.py research/quality-measurement/connected-chapters-20260916/continuation-claim.json
```

No production source or defaults change in this result. The reader-facing report and reading
copies remain local; committed artifacts contain identifiers, numerical controls and
methodological conclusions.

## Validation

Final canonical `tools/check.py handoff` passed: 5,338 tests passed, 20 skipped, 90.11%
coverage, clean lint/types/diff/lock checks, built wheel and clean corpus-history audit.
The local `runs/connected-chapters-20260916-results-handoff.log` is content-addressed by the
reading record. The check includes unrelated existing checkout changes, which are excluded
from this result commit.
