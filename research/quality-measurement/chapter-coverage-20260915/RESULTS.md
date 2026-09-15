# Fixed-story chapter coverage: completed

Registration commit: ca5b802. Control: d247331. Treatment: aa33e6a.
The frozen [RUNBOOK](RUNBOOK.md) owns scope, limits and interpretation rules.

Two previously observed source-story units were reused in both arms. All four books reached
two chapters, with one outline call and one writer output per reached chapter. The run used
the registered production workflow, with no redraw, manual repair or implicit continuation.

| Book | Chapter 1 words | Chapter 2 words | Calls | Recorded Usage.total |
| --- | ---: | ---: | ---: | ---: |
| A2 | 1,470 | 1,510 | 12 | 227,565 |
| B2 | 1,562 | 1,546 | 12 | 227,547 |
| A4 | 1,555 | 1,504 | 12 | 230,237 |
| B4 | 1,464 | 1,497 | 12 | 248,575 |
| Total | 6,051 | 6,057 | 48 | 933,924 |

All 36 workflow steps returned zero. No provider failure, unknown usage, narrative retry or
terminal job occurred. Final queues were empty. Calls include ordinary health probes.
The recorded dispatch interval was 2026-09-15 15:53:28.686196–16:24:02.292744 UTC.

## Controls and attribution

- Both offline request-difference controls passed. Each control exactly reproduced its
  source outline request. Only the registered layout, rule, schema and profile differed in B.
- All four first live requests equalled their frozen preflight requests.
- All recorded transport and step controls passed. Every store rebuilt with zero unattributed
  revisions. Author briefs and generated experience briefs were retained.
- Both B outlines reconciled six chapter groups, and all twelve coverage items were retained.
- Every reached scene's job-bound brief matched its outline and was rendered fully in the
  actual writer request. All eight policy decisions used one narrative attempt.
- Four accepted texts equal their writer outputs after trimming. The other four reproduce
  exactly after the existing production dash/markup cleanup, also used in A. No narrative
  rewrite is inferred from those formatting differences.

[evidence.json](evidence.json) contains transport, resource and volume records.
[handoff-evidence.json](handoff-evidence.json) contains deterministic request, coverage,
scene-plan and writer-input checks. Rebuild the latter after `run.py audit` with:

```powershell
uv run python research/quality-measurement/chapter-coverage-20260915/inspect_handoff.py
```

The implementation handoff and preregistration handoff passed. Final verification and reading
artifact hashes are recorded in [reading-record.json](reading-record.json).

## Interpretation boundary

The claim remains **OBSERVED**. Correct grouping, retained explanations and exact transmission
do not establish feasible coverage, earlier completion, enjoyment or popularity. The live
comparison exercises the planning handoff; upstream invention/development layout changes
were tested offline. These known cases are not an unseen transfer sample.

The located reading did not establish the intended improvement in early completion. A
candidate follow-up concerns the treatment of generic dramatic-function labels in a
concept-backed outline: a label for a larger arc may be interpreted as an exclusive limit
on local chapter activity. That interpretation is a hypothesis, not a causal result or a
qualified editorial mechanism. No production prompt or acceptance policy consumes these
reading notes.

Full generated material and located interpretations remain in the ignored run directory:
`runs/chapter-coverage-20260915/REPORT.md` and `READING-NOTES.md`. Their hashes identify the
readings without promoting them into independent reader labels or a quality score.
